"""Model backends with deterministic decoding (ported from regbench).

ollama:<name>   local Ollama server (default; all layers on GPU)
hf:<dir>[+<adapter dir>]  local transformers model in 4-bit NF4, greedy decoding (training env only;
                used to compare a base model with its QLoRA adapter under identical decoding)
mock:<name>     canned answers for tests; never used for reported results
"""
import json
import os
import time

import requests

# 127.0.0.1, not localhost: on Windows localhost tries IPv6 first and adds ~2 s per request
OLLAMA = os.environ.get("OLLAMA_HOST_URL", "http://127.0.0.1:11434")
NUM_GPU = int(os.environ.get("FINEVAL_NUM_GPU", "99"))

MAX_TOKENS = {"concept_tagging": 64, "fact_extraction": 1024, "financial_calc": 1024, "filing_qa": 256}
NUM_CTX = {"concept_tagging": 4096, "fact_extraction": 8192, "financial_calc": 2048, "filing_qa": 4096}


def chat(model, user, *, system=None, temperature=0.0, seed=0, max_tokens=512, num_ctx=4096,
         retries=3, timeout=900):
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
    if model.startswith("mock:"):
        return _mock(model, messages)
    if model.startswith("hf:"):
        return _hf(model[3:], messages, max_tokens)
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


_HF = {}


def _hf(spec, messages, max_tokens):
    """Greedy decoding with a local safetensors model, optionally with a PEFT adapter."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    if spec not in _HF:
        base, _, adapter = spec.partition("+")
        tok = AutoTokenizer.from_pretrained(base)
        m = AutoModelForCausalLM.from_pretrained(
            base, use_safetensors=True, trust_remote_code=False, device_map={"": 0},
            quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                                   bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True))
        if adapter:
            from peft import PeftModel
            m = PeftModel.from_pretrained(m, adapter)
        _HF.clear()
        _HF[spec] = (tok, m.eval())
    tok, m = _HF[spec]
    ids = tok.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt", return_dict=True).to(0)
    t0 = time.time()
    with torch.no_grad():
        out = m.generate(**ids, max_new_tokens=max_tokens, do_sample=False, pad_token_id=tok.eos_token_id)
    new = out[0, ids["input_ids"].shape[1]:]
    return {"text": tok.decode(new, skip_special_tokens=True), "prompt_tokens": int(ids["input_ids"].shape[1]),
            "eval_count": int(new.shape[0]), "latency_s": round(time.time() - t0, 3)}


def model_digest(model) -> str | None:
    """For hf: models, the SHA-256 of the adapter weights (or None for a bare base model)."""
    if model.startswith("hf:"):
        import hashlib
        from pathlib import Path
        _, _, adapter = model[3:].partition("+")
        f = Path(adapter) / "adapter_model.safetensors"
        return hashlib.sha256(f.read_bytes()).hexdigest() if adapter and f.exists() else None
    # Ollama: the content digest of the model weights, recorded with every run.
    if not model.startswith("ollama:"):
        return None
    name = model.split(":", 1)[1]
    r = requests.get(f"{OLLAMA}/api/tags", timeout=60)
    r.raise_for_status()
    for m in r.json().get("models", []):
        if m["name"] == name or m["name"] == f"{name}:latest":
            return m["digest"]
    raise ValueError(f"{name} is not installed in Ollama")
