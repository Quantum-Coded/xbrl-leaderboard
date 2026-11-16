"""Profile latency and peak memory of one model x track on a fixed list of FinCL items.

    python -I scripts/profile_runs.py --model ollama:qwen2.5:3b --track tools_noorac [--n 100] [--machine NAME]

Same items, prompts and decoding as fineval.run (greedy, seed 0, same num_ctx rule), so every model
and machine is measured on identical inputs. Procedure:
  1. unload every model from Ollama (keep_alive=0), so the run starts from an empty server;
  2. record baseline memory, then one unrecorded warm-up call (loads the model);
  3. call the model once per item, recording wall latency and Ollama's own durations;
  4. a background thread samples memory every 0.2 s for the whole run:
       all machines  Ollama GET /api/ps  (size = model memory, size_vram = part on the GPU)
       NVIDIA        nvidia-smi memory.used (whole GPU; baseline recorded before loading)
       macOS/Linux   summed resident memory (RSS) of all ollama processes
Writes <results>/profile/<machine>/<model>__<track>__n<N>.json, where <results> is results/ or the
FINEVAL_RESULTS folder (e.g. results/mac/m2). Refuses to run on battery unless --allow-battery.
Only the standard library and requests are used, so it runs unchanged on Windows and macOS.
"""
import argparse
import json
import platform
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fineval import data, llm, prompts, run, scorers  # noqa: E402

SAMPLE_EVERY_S = 0.2


def sh(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def on_ac_power():
    """True on mains power, False on battery, None if unknown (e.g. a desktop without a battery API)."""
    sysname = platform.system()
    if sysname == "Darwin":
        out = sh(["pmset", "-g", "batt"])
        return None if not out else "AC Power" in out
    if sysname == "Windows":
        out = sh(["powershell", "-NoProfile", "-Command",
                  "Add-Type -AssemblyName System.Windows.Forms;"
                  "[System.Windows.Forms.SystemInformation]::PowerStatus.PowerLineStatus"])
        return {"Online": True, "Offline": False}.get(out)
    p = Path("/sys/class/power_supply/AC/online")
    return p.read_text().strip() == "1" if p.exists() else None


def machine_info():
    sysname = platform.system()
    info = {"os": platform.platform(), "python": platform.python_version(), "arch": platform.machine()}
    if sysname == "Darwin":
        info["chip"] = sh(["sysctl", "-n", "machdep.cpu.brand_string"])
        mem = sh(["sysctl", "-n", "hw.memsize"])
        info["ram_gb"] = round(int(mem) / 2**30, 1) if mem.isdigit() else None
    elif sysname == "Windows":
        info["cpu"] = sh(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"])
        mem = sh(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"])
        info["ram_gb"] = round(int(mem) / 2**30, 1) if mem.isdigit() else None
    else:
        info["cpu"] = platform.processor()
    if shutil.which("nvidia-smi"):
        info["gpu"] = sh(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"])
    return info


def default_machine_name():
    if platform.system() == "Darwin":
        chip = sh(["sysctl", "-n", "machdep.cpu.brand_string"])            # e.g. "Apple M2 Pro"
        return re.sub(r"[^a-z0-9]+", "-", chip.lower().replace("apple", "")).strip("-") or "mac"
    if shutil.which("nvidia-smi"):
        gpu = sh(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"]).splitlines()[:1]
        if gpu:
            return re.sub(r"[^a-z0-9]+", "-", gpu[0].lower().replace("nvidia geforce", "")).strip("-")
    return platform.node().lower() or "machine"


class MemorySampler(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.stop = threading.Event()
        self.peak = {"ollama_size_mib": 0, "ollama_size_vram_mib": 0, "gpu_used_mib": 0, "ollama_rss_mib": 0}
        self.samples = 0
        self.nvidia = bool(shutil.which("nvidia-smi"))
        self.posix = platform.system() in ("Darwin", "Linux")

    @staticmethod
    def gpu_used():
        out = sh(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"])
        return int(out.splitlines()[0]) if out and out.splitlines()[0].strip().isdigit() else 0

    @staticmethod
    def ollama_rss():
        out = sh(["ps", "-axo", "rss=,comm="])
        return sum(int(l.split(None, 1)[0]) for l in out.splitlines()
                   if "ollama" in l.lower() and l.split(None, 1)[0].isdigit()) // 1024

    def read(self):
        cur = {}
        try:
            ps = requests.get(f"{llm.OLLAMA}/api/ps", timeout=5).json().get("models", [])
            cur["ollama_size_mib"] = sum(m.get("size", 0) for m in ps) // 2**20
            cur["ollama_size_vram_mib"] = sum(m.get("size_vram", 0) for m in ps) // 2**20
        except requests.RequestException:
            pass
        if self.nvidia:
            cur["gpu_used_mib"] = self.gpu_used()
        if self.posix:
            cur["ollama_rss_mib"] = self.ollama_rss()
        return cur

    def run(self):
        while not self.stop.is_set():
            for k, v in self.read().items():
                self.peak[k] = max(self.peak[k], v)
            self.samples += 1
            self.stop.wait(SAMPLE_EVERY_S)


def fixed_items(n):
    """Every k-th FinCL primary item in uid order: the same list for every model, track and machine."""
    items = sorted((i for i in data.items("concept_tagging") if i["subset"] == "fincl_subset" and i["primary"]),
                   key=lambda i: i["uid"])
    step = max(1, len(items) // n)
    return items[::step][:n]


def call(name, system, user, num_ctx, max_tokens):
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
    body = {"model": name, "messages": messages, "stream": False,
            "options": {"temperature": 0.0, "seed": 0, "num_predict": max_tokens, "num_ctx": num_ctx,
                        "num_gpu": llm.NUM_GPU}}
    t0 = time.perf_counter()
    r = requests.post(f"{llm.OLLAMA}/api/chat", json=body, timeout=900)
    wall = time.perf_counter() - t0
    r.raise_for_status()
    return r.json(), wall


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, max(0, round(q * (len(xs) - 1))))]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="ollama:<tag>")
    ap.add_argument("--track", default="closed", choices=prompts.TRACKS)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--machine", default=None, help="folder name for this machine (default: from GPU or chip)")
    ap.add_argument("--allow-battery", action="store_true")
    args = ap.parse_args(argv)
    if not args.model.startswith("ollama:"):
        raise SystemExit("profiling is defined for Ollama models only")
    name = args.model.split(":", 1)[1]
    power = on_ac_power()
    if power is False and not args.allow_battery:
        raise SystemExit("on battery: plug in (or pass --allow-battery; it is recorded in the output)")
    version = requests.get(f"{llm.OLLAMA}/api/version", timeout=5).json().get("version")
    machine = args.machine or default_machine_name()

    # 1. empty server
    for m in requests.get(f"{llm.OLLAMA}/api/ps", timeout=5).json().get("models", []):
        requests.post(f"{llm.OLLAMA}/api/generate", json={"model": m["name"], "keep_alive": 0}, timeout=60)
    time.sleep(2)
    sampler = MemorySampler()
    baseline = sampler.read()

    items = fixed_items(args.n)
    max_tokens = llm.MAX_TOKENS["concept_tagging"]
    # 2. warm-up (loads the model; not recorded)
    sampler.start()
    s, u, _ = prompts.build(items[0], args.track)
    call(name, s, u, max(llm.NUM_CTX["concept_tagging"], run.ctx_for(s, u, max_tokens)), max_tokens)
    after_load = dict(sampler.peak)

    # 3. timed calls
    rows = []
    for it in items:
        s, u, _ = prompts.build(it, args.track)
        num_ctx = max(llm.NUM_CTX["concept_tagging"], run.ctx_for(s, u, max_tokens))
        out, wall = call(name, s, u, num_ctx, max_tokens)
        ns = 1e9
        rows.append({"uid": it["uid"], "wall_s": round(wall, 4),
                     "total_s": round(out.get("total_duration", 0) / ns, 4),
                     "load_s": round(out.get("load_duration", 0) / ns, 4),
                     "prompt_eval_s": round(out.get("prompt_eval_duration", 0) / ns, 4),
                     "eval_s": round(out.get("eval_duration", 0) / ns, 4),
                     "prompt_tokens": out.get("prompt_eval_count"), "eval_tokens": out.get("eval_count"),
                     "num_ctx": num_ctx,
                     "exact": scorers.concept_exact(out["message"]["content"], it["gold"])["exact"]})
    sampler.stop.set()
    sampler.join()

    ps = requests.get(f"{llm.OLLAMA}/api/ps", timeout=5).json().get("models", [])
    lat = [r["wall_s"] for r in rows]
    gen_tps = [r["eval_tokens"] / r["eval_s"] for r in rows if r["eval_s"] and r["eval_tokens"]]
    res = {
        "model": args.model, "model_digest": llm.model_digest(args.model), "track": args.track,
        "n": len(rows), "items": [r["uid"] for r in rows], "ollama_version": version,
        "machine_name": machine, "machine": machine_info(), "on_ac_power": power,
        "num_gpu": llm.NUM_GPU, "code_commit": run.git_commit(), "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "loaded_model": [{k: m.get(k) for k in ("name", "size", "size_vram", "details")} for m in ps],
        "summary": {
            "accuracy_on_profiled_items": round(sum(r["exact"] for r in rows) / len(rows), 4),
            "latency_median_s": round(statistics.median(lat), 4),
            "latency_p90_s": round(pct(lat, 0.9), 4),
            "latency_mean_s": round(statistics.mean(lat), 4),
            "gen_tokens_per_s_median": round(statistics.median(gen_tps), 1) if gen_tps else None,
            "prompt_tokens_median": statistics.median(r["prompt_tokens"] or 0 for r in rows),
            "memory_baseline_mib": baseline,
            "memory_peak_after_load_mib": after_load,
            "memory_peak_mib": sampler.peak,
            "gpu_peak_minus_baseline_mib": (sampler.peak["gpu_used_mib"] - baseline.get("gpu_used_mib", 0))
            if sampler.nvidia else None,
            "memory_samples": sampler.samples,
        },
        "per_item": rows,
    }
    safe = name.replace(":", "-").replace("/", "_")
    dest = run.RESULTS / "profile" / machine / f"{safe}__{args.track}__n{len(rows)}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res["summary"], indent=1))
    print("wrote", dest.relative_to(ROOT) if dest.is_relative_to(ROOT) else dest)
    return dest


if __name__ == "__main__":
    main()
