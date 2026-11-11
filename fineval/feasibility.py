"""Phase 0 feasibility: generation speed, prompt speed and VRAM per model and context size.

    python -I -m fineval.feasibility --models llama3.1:8b qwen2.5:7b mistral:7b qwen2.5:3b gemma2:9b

Writes results/feasibility.json. Each setting sends one prompt of roughly the context size being tested
(filler text from a pinned source file) and asks for a fixed number of tokens; VRAM is read from
nvidia-smi while the model is loaded, and Ollama's /api/ps reports how much of the model is on the GPU.
"""
import argparse
import json
import subprocess

import requests

from .fetch import ROOT
from .llm import NUM_GPU, OLLAMA

OUT = ROOT / "results" / "feasibility.json"
FILLER = ROOT / "data" / "raw" / "papers" / "financebench_2311.11944v1.txt"


def vram_mib() -> int:
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True, check=True).stdout
    return int(out.strip().splitlines()[0])


def on_gpu_share(name: str):
    for m in requests.get(f"{OLLAMA}/api/ps", timeout=60).json().get("models", []):
        if m["name"] in (name, f"{name}:latest"):
            return round(m["size_vram"] / m["size"], 3) if m.get("size") else None
    return None


def probe(name: str, ctx: int, gen: int = 128) -> dict:
    words = FILLER.read_text(encoding="utf-8").split()
    prompt = " ".join(words[: int((ctx - gen - 256) * 0.6)]) + "\n\nSummarise the text above in detail."
    body = {"model": name, "messages": [{"role": "user", "content": prompt}], "stream": False,
            "options": {"temperature": 0, "seed": 0, "num_predict": gen, "num_ctx": ctx, "num_gpu": NUM_GPU}}
    try:
        r = requests.post(f"{OLLAMA}/api/chat", json=body, timeout=1800)
        r.raise_for_status()
        o = r.json()
    except requests.RequestException as e:
        return {"ctx": ctx, "error": str(e)[:200]}
    return {"ctx": ctx, "prompt_tokens": o["prompt_eval_count"], "gen_tokens": o["eval_count"],
            "prompt_tok_s": round(o["prompt_eval_count"] / (o["prompt_eval_duration"] / 1e9), 1),
            "gen_tok_s": round(o["eval_count"] / (o["eval_duration"] / 1e9), 1),
            "load_s": round(o.get("load_duration", 0) / 1e9, 2), "vram_mib": vram_mib(), "gpu_share": on_gpu_share(name)}


def unload(name: str):
    requests.post(f"{OLLAMA}/api/generate", json={"model": name, "keep_alive": 0}, timeout=120)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--ctx", nargs="+", type=int, default=[2048, 4096, 8192])
    a = ap.parse_args(argv)
    res = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    for m in a.models:
        res[m] = []
        for c in a.ctx:
            unload(m)
            r = probe(m, c)
            print(m, r, flush=True)
            res[m].append(r)
        unload(m)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
