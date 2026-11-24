"""Run fineval jobs in short chunks with pauses, so a laptop GPU is never under load for hours at a time.

    python -I scripts/safe_run.py --job ollama:gemma2:2b,financial_calc,tools --job ollama:mistral:7b,financial_calc,closed
    python -I scripts/safe_run.py --dry-run --job ...     (print the checks and the plan, run nothing)

Long unbroken GPU runs on the Windows laptop (RTX 4050) led to restarts and Ollama server errors on
18 Nov 2026. This wrapper calls `python -I -m fineval.run ... --limit CHUNK` repeatedly (the runner resumes,
so results are identical to one long run) and between chunks:
  - stops if the laptop is on battery;
  - waits while the GPU is hotter than --cool-to (default 65 C); if a chunk reached --max-temp (default
    80 C), the next chunk is halved (never below 10 items). Chunks are never killed mid-way, so no answer
    is written half-way;
  - pauses --pause seconds (default 60);
  - stops the whole plan on the first failed chunk (no retry loop) or when a run has more than
    --max-server-errors items recorded as server_error;
  - scores each job when it is complete.
Every check and decision is appended to results/logs/safe_run.log.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from profile_runs import MemorySampler, on_ac_power  # noqa: E402
from fineval import data, run  # noqa: E402

LOG = ROOT / "results/logs/safe_run.log"


def log(msg):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def gpu_temp():
    return MemorySampler.gpu_used()[1] if MemorySampler().nvidia else None


def progress(model, task, track):
    name = run.run_name(model, task, track, 0, None)
    out = run.GEN / f"{name}.jsonl"
    rows = [json.loads(l) for l in out.open(encoding="utf-8")] if out.exists() else []
    total = len(data.sample(task, None, seed=0))
    return name, len(rows), total, sum(r["status"] == "server_error" for r in rows)


def cool_down(target, limit_s=1800):
    t0 = time.time()
    while (t := gpu_temp()) is not None and t > target:
        if time.time() - t0 > limit_s:
            return False
        log(f"GPU at {t} C, waiting to cool below {target} C")
        time.sleep(30)
    return True


def run_chunk(cmd):
    """Run one chunk to the end; return (exit code, hottest GPU temperature seen)."""
    p = subprocess.Popen(cmd, cwd=ROOT)
    hottest = 0
    while p.poll() is None:
        hottest = max(hottest, gpu_temp() or 0)
        time.sleep(5)
    return p.returncode, hottest


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", action="append", required=True, help="model,task,track e.g. ollama:gemma2:2b,financial_calc,tools")
    ap.add_argument("--chunk", type=int, default=50)
    ap.add_argument("--pause", type=int, default=60)
    ap.add_argument("--cool-to", type=int, default=65)
    ap.add_argument("--max-temp", type=int, default=80)
    ap.add_argument("--max-server-errors", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    jobs = [tuple(j.split(",")) for j in args.job]
    log(f"plan: {jobs}  chunk={args.chunk} pause={args.pause}s cool_to={args.cool_to}C max_temp={args.max_temp}C")
    for model, task, track in jobs:
        name, done, total, errs = progress(model, task, track)
        log(f"  {name}: {done}/{total} done, {errs} server errors")
    log(f"  power: {'mains' if on_ac_power() else 'battery or unknown'}, GPU temperature: {gpu_temp()} C")
    if args.dry_run:
        return 0
    py = sys.executable
    chunk = args.chunk
    for model, task, track in jobs:
        while True:
            name, done, total, errs = progress(model, task, track)
            if errs > args.max_server_errors:
                log(f"STOP: {name} has {errs} server errors (> {args.max_server_errors})")
                return 1
            if done >= total:
                break
            if on_ac_power() is False:
                log("STOP: on battery")
                return 1
            if not cool_down(args.cool_to):
                log("STOP: GPU did not cool down within 30 minutes")
                return 1
            log(f"{name}: chunk of {chunk} from {done}/{total}")
            rc, hottest = run_chunk([py, "-I", "-m", "fineval.run", "--model", model, "--task", task, "--track",
                                     track, "--seed", "0", "--limit", str(chunk)])
            log(f"  chunk finished, exit {rc}, hottest GPU {hottest} C")
            if hottest >= args.max_temp and chunk > 10:
                chunk = max(10, chunk // 2)
                log(f"  GPU reached {args.max_temp} C: next chunks are {chunk} items")
            if rc != 0:
                log(f"STOP: chunk failed with exit code {rc}")
                return 1
            time.sleep(args.pause)
        subprocess.run([py, "-I", "-m", "fineval.score", "--run", name], cwd=ROOT, capture_output=True)
        log(f"{name}: complete and scored")
    log("ALL JOBS DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
