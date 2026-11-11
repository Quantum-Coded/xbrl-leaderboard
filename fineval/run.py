"""Generate model outputs for one (model, task, track) run. Resumable: finished items are skipped.

    python -I -m fineval.run --model ollama:qwen2.5:7b --task financial_calc --track closed [--n 300]

Writes results/generations/<run>.jsonl (one line per item) and <run>.meta.json (model digest,
context sizes, sample, code version). Context length is chosen per item so prompts are never
silently truncated; an item that would not fit FinEval's cap is recorded as `skipped_context`
and scores 0.
"""
import argparse
import hashlib
import json
import subprocess
import time

from . import data, llm, prompts
from .fetch import ROOT

GEN = ROOT / "results" / "generations"
CTX_CAP = 8192
CHARS_PER_TOKEN = 3.0          # conservative estimate; the true count is checked after the call


def run_name(model, task, track, seed, n):
    if model.startswith("hf:"):                     # hf:models/base/X+models/qlora-y -> hf-X+qlora-y
        model = "hf-" + "+".join(p.rstrip("/").split("/")[-1] for p in model[3:].split("+"))
    safe = model.replace("ollama:", "").replace(":", "-").replace("/", "_")
    return f"{safe}__{task}__{track}__s{seed}" + (f"__n{n}" if n else "")


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except OSError:
        return None


def ctx_for(system, user, max_tokens):
    est = int((len(system or "") + len(user)) / CHARS_PER_TOKEN) + max_tokens + 64
    return ((est + 1023) // 1024) * 1024


def generate(item, model, track, seed):
    system, user, log = prompts.build(item, track)
    max_tokens = llm.MAX_TOKENS[item["task"]]
    num_ctx = max(llm.NUM_CTX[item["task"]], ctx_for(system, user, max_tokens))
    rec = {"uid": item["uid"], "cluster_id": item["cluster_id"], "task": item["task"], "track": track,
           "prompt_sha1": hashlib.sha1(((system or "") + "\n" + user).encode("utf-8")).hexdigest(), "tool_log": log}
    if num_ctx > CTX_CAP:
        return {**rec, "status": "skipped_context", "output": "", "num_ctx": num_ctx}
    res = llm.chat(model, user, system=system, seed=seed, max_tokens=max_tokens, num_ctx=num_ctx)
    out, status = res["text"], "ok"
    if res.get("prompt_tokens") and res["prompt_tokens"] + 1 >= num_ctx:
        status = "truncated"                       # should not happen; reported if it does
    if item["task"] == "financial_calc" and track == "tools":
        out, calc = prompts.finish_tools_calc(out)
        rec["tool_log"] = {**log, "calc": calc}
    return {**rec, "status": status, "raw_output": res["text"], "output": out, "num_ctx": num_ctx,
            "prompt_tokens": res.get("prompt_tokens"), "eval_count": res.get("eval_count"), "latency_s": res.get("latency_s")}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--task", required=True, choices=["concept_tagging", "fact_extraction", "financial_calc", "filing_qa"])
    ap.add_argument("--track", default="closed", choices=prompts.TRACKS)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n", type=int, default=None, help="fixed stratified subset size (default: all items)")
    ap.add_argument("--limit", type=int, default=None, help="stop after this many new items (smoke tests)")
    args = ap.parse_args(argv)
    if args.task == "fact_extraction" and args.track == "tools":
        raise SystemExit("fact_extraction has no tool-assisted variant")

    items = data.sample(args.task, args.n, seed=0)
    name = run_name(args.model, args.task, args.track, args.seed, args.n)
    GEN.mkdir(parents=True, exist_ok=True)
    out = GEN / f"{name}.jsonl"
    meta = GEN / f"{name}.meta.json"
    if not meta.exists():
        meta.write_text(json.dumps({
            "model": args.model, "model_digest": llm.model_digest(args.model), "runtime": llm.runtime_version(args.model), "task": args.task, "track": args.track,
            "seed": args.seed, "n": args.n, "items": [i["uid"] for i in items], "max_tokens": llm.MAX_TOKENS[args.task],
            "num_ctx_default": llm.NUM_CTX[args.task], "ctx_cap": CTX_CAP, "code_commit": git_commit(),
            "started": time.strftime("%Y-%m-%dT%H:%M:%S")}, indent=1), encoding="utf-8")
    done = {json.loads(l)["uid"] for l in out.open(encoding="utf-8")} if out.exists() else set()
    todo = [i for i in items if i["uid"] not in done]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{name}: {len(done)} done, {len(todo)} to go", flush=True)
    t0 = time.time()
    with out.open("a", encoding="utf-8", newline="\n") as f:
        for k, it in enumerate(todo, 1):
            f.write(json.dumps(generate(it, args.model, args.track, args.seed), ensure_ascii=False) + "\n")
            f.flush()
            if k % 25 == 0:
                print(f"  {k}/{len(todo)}  {(time.time() - t0) / k:.1f}s/item", flush=True)
    return out


if __name__ == "__main__":
    main()
