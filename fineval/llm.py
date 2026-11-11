"""Model backends with deterministic decoding (ported from regbench).

ollama:<name>   local Ollama server (default; all layers on GPU)
mock:<name>     canned answers for tests; never used for reported results
"""
import json
import os
import time

import requests

OLLAMA = os.environ.get("OLLAMA_HOST_URL", "http://localhost:11434")
NUM_GPU = int(os.environ.get("FINEVAL_NUM_GPU", "99"))

MAX_TOKENS = {"concept_tagging": 64, "fact_extraction": 1024, "financial_calc": 1024, "filing_qa": 256}
NUM_CTX = {"concept_tagging": 4096, "fact_extraction": 8192, "financial_calc": 2048, "filing_qa": 4096}


def chat(model, user, *, system=None, temperature=0.0, seed=0, max_tokens=512, num_ctx=4096,
         retries=3, timeout=900):
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
    if model.startswith("mock:"):
        return _mock(model, messages)
    name = model.split(":", 1)[1] if model.startswith("ollama:") else model
    body = {"model": name, "messages": messages, "stream": False,
            "options": {"temperature": temperature, "seed": seed, "num_predict": max_tokens,
                        "num_ctx": num_ctx, "num_gpu": NUM_GPU}}
    for attempt in range(retries):
        try:
            r = requests.post(f"{OLLAMA}/api/chat", json=body, timeout=timeout)
            r.raise_for_status()
            out = r.json()
            return {"text": out["message"]["content"], "prompt_tokens": out.get("prompt_eval_count"),
                    "eval_count": out.get("eval_count"), "latency_s": round(out.get("total_duration", 0) / 1e9, 3)}
        except (requests.RequestException, KeyError, json.JSONDecodeError):
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))


def _mock(model, messages):
    """mock:echo repeats the last user line; mock:fixed:<text> always answers <text>."""
    rest = model.split(":", 2)
    text = rest[2] if len(rest) > 2 and rest[1] == "fixed" else messages[-1]["content"].splitlines()[-1]
    return {"text": text, "prompt_tokens": None, "eval_count": None, "latency_s": 0.0}


def model_digest(model) -> str | None:
    """Ollama's content digest of the model weights, recorded with every run."""
    if not model.startswith("ollama:"):
        return None
    name = model.split(":", 1)[1]
    r = requests.get(f"{OLLAMA}/api/tags", timeout=60)
    r.raise_for_status()
    for m in r.json().get("models", []):
        if m["name"] == name or m["name"] == f"{name}:latest":
            return m["digest"]
    raise ValueError(f"{name} is not installed in Ollama")
