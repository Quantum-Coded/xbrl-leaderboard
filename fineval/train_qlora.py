"""QLoRA fine-tuning on FinEval's training data (Phase 7). Needs a CUDA GPU; run with the training
environment (system torch + transformers + bitsandbytes, plus peft), not the CPU venv:

    python -m fineval.train_qlora --base <local HF model dir> --data fincl --out models/qwen3b-fincl --smoke
    python -m fineval.train_qlora --base <local HF model dir> --data fincl --out models/qwen3b-fincl

--smoke runs 200 steps and reports whether loss fell on held-out training examples (the
feasibility gate). Held-out examples come from the training split only, grouped by source item,
so no test data is used for any choice. Weights are loaded from safetensors only.
"""
import argparse
import json
import math
import random
from pathlib import Path

from .build import OUT

SFT = OUT / "sft"


def split_examples(rows, dev_share=0.05, seed=0):
    """Hold out whole source items (uid groups), never single examples of an item."""
    uids = sorted({r["uid"] for r in rows})
    rng = random.Random(seed)
    dev = set(rng.sample(uids, max(1, int(len(uids) * dev_share))))
    return [r for r in rows if r["uid"] not in dev], [r for r in rows if r["uid"] in dev]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="local directory with a HF model in safetensors")
    ap.add_argument("--data", choices=["fincl", "finni"], required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--max-len", type=int, default=1024)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    torch.manual_seed(a.seed)
    rows = [json.loads(l) for l in (SFT / f"{a.data}.jsonl").open(encoding="utf-8")]
    train, dev = split_examples(rows, seed=a.seed)
    tok = AutoTokenizer.from_pretrained(a.base)
    model = AutoModelForCausalLM.from_pretrained(
        a.base, use_safetensors=True, trust_remote_code=False, device_map={"": 0},
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                               bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True))
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(model, LoraConfig(r=a.rank, lora_alpha=2 * a.rank, lora_dropout=0.05, task_type="CAUSAL_LM",
                                             target_modules=["q_proj", "k_proj", "v_proj", "o_proj"]))

    def encode(r):
        prompt = tok.apply_chat_template([{"role": "user", "content": r["prompt"]}], tokenize=False, add_generation_prompt=True)
        p = tok(prompt, add_special_tokens=False)["input_ids"]
        c = tok(r["completion"] + tok.eos_token, add_special_tokens=False)["input_ids"]
        ids = (p + c)[-a.max_len:]
        labels = ([-100] * len(p) + c)[-a.max_len:]          # loss on the answer only
        return torch.tensor([ids]), torch.tensor([labels])

    @torch.no_grad()
    def dev_loss(n=100):
        model.eval()
        ls = [model(input_ids=i.cuda(), labels=l.cuda()).loss.item() for i, l in map(encode, dev[:n])]
        model.train()
        return sum(ls) / len(ls)

    steps = 200 if a.smoke else math.ceil(len(train) * a.epochs)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr)
    order = list(range(len(train)))
    random.Random(a.seed).shuffle(order)
    log = {"base": a.base, "data": a.data, "train_examples": len(train), "dev_examples": len(dev), "steps": steps,
           "lr": a.lr, "rank": a.rank, "seed": a.seed, "dev_loss_before": dev_loss()}
    model.train()
    for s in range(steps):
        i, l = encode(train[order[s % len(order)]])
        loss = model(input_ids=i.cuda(), labels=l.cuda()).loss
        loss.backward()
        opt.step()
        opt.zero_grad()
        if (s + 1) % 50 == 0:
            print(f"step {s + 1}/{steps} loss {loss.item():.4f}", flush=True)
    log["dev_loss_after"] = dev_loss()
    log["gate_passed"] = log["dev_loss_after"] < log["dev_loss_before"]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if not a.smoke:
        model.save_pretrained(out)
    (out / "train_log.json").write_text(json.dumps(log, indent=1), encoding="utf-8")
    print(json.dumps(log, indent=1))


if __name__ == "__main__":
    main()
