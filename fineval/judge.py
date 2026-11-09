"""LLM judge for filing QA (qa_judge@v1) and its human audit (Phase 8).

Labels follow FinanceBench's human grading (Islam et al. 2023, Table 2): CORRECT, INCORRECT,
FAILED (refused or did not answer). Rules carried over from our COLING judge study:
  * a cross-family judge (never the model being graded),
  * refusals / "cannot determine" answers are FAILED by a regex before the judge sees them,
  * the gold answer and its justification are given; the filing is not,
  * greedy decoding, cached per (run, judge, uid).

    python -I -m fineval.judge --run <run> --judge ollama:qwen2.5:7b
    python -I -m fineval.judge --export-audit <run> --n 60    # CSV for two human labellers
    python -I -m fineval.judge --audit <labels.csv>           # agreement, kappa, TPR/TNR
"""
import argparse
import csv
import json
import random
import re
from collections import Counter

from . import data, llm
from .fetch import ROOT
from .run import GEN
from .stats import bootstrap_ci

JUDGE_DIR = ROOT / "results" / "judgements"
AUDIT_DIR = ROOT / "review" / "judge_audit"
LABELS = ("CORRECT", "INCORRECT", "FAILED")

ABSTAIN = re.compile(r"(cannot|can't|can not|unable to|not able to)\s+(determine|answer|find|provide|access|calculate)"
                     r"|(do not|don't) have (access|enough|the necessary|sufficient)"
                     r"|not (provided|available|included) in the (pages|context|information|filing)"
                     r"|^\s*(i don't know|unknown|n/?a)\s*\.?\s*$", re.I)

JUDGE_PROMPT = """You are grading an answer to a question about a company's SEC filing.

Question: {question}
Reference answer: {gold}
Reference justification: {justification}

Candidate answer: {answer}

Grade the candidate against the reference:
- CORRECT: it states the same figure or conclusion as the reference. Minor rounding or formatting
  differences are fine; extra correct detail is fine.
- INCORRECT: it gives a different figure or conclusion, or a contradicting one.
- FAILED: it does not answer (refuses, says the information is unavailable, or only asks for more context).

Reply with exactly one word: CORRECT, INCORRECT or FAILED."""


def parse_label(text: str) -> str | None:
    m = re.search(r"\b(CORRECT|INCORRECT|FAILED)\b", text.upper())
    return m.group(1) if m else None


def judge_one(item, answer, judge_model):
    if not answer.strip() or ABSTAIN.search(answer):
        return {"label": "FAILED", "by": "abstain_rule"}
    p = JUDGE_PROMPT.format(question=item["input"]["question"], gold=item["gold"]["answer"],
                            justification=item["gold"].get("justification") or "(none)", answer=answer.strip()[:3000])
    out = llm.chat(judge_model, p, max_tokens=8, num_ctx=4096)["text"]
    return {"label": parse_label(out) or "INCORRECT", "by": "judge", "raw": out, "unparsed": parse_label(out) is None}


def family(model: str) -> str:
    """'ollama:qwen2.5:7b' -> 'qwen', 'ollama:llama3.1:8b' -> 'llama'."""
    name = model.split(":", 1)[1] if model.startswith(("ollama:", "mock:")) else model
    return re.match(r"[a-z]+", name.lower()).group(0)


def judge_run(run: str, judge_model: str) -> dict:
    meta = json.loads((GEN / f"{run}.meta.json").read_text(encoding="utf-8"))
    if meta["task"] != "filing_qa":
        raise SystemExit("judge applies to filing_qa runs only")
    if family(judge_model) == family(meta["model"]):
        raise SystemExit("judge and graded model must be from different families")
    gens = {json.loads(l)["uid"]: json.loads(l) for l in (GEN / f"{run}.jsonl").open(encoding="utf-8")}
    by_uid = {i["uid"]: i for i in data.items("filing_qa")}
    safe = judge_model.replace("ollama:", "").replace(":", "-")
    out = JUDGE_DIR / f"{run}__judge-{safe}.jsonl"
    JUDGE_DIR.mkdir(parents=True, exist_ok=True)
    done = {json.loads(l)["uid"]: json.loads(l) for l in out.open(encoding="utf-8")} if out.exists() else {}
    with out.open("a", encoding="utf-8", newline="\n") as f:
        for uid in meta["items"]:
            if uid in done:
                continue
            g = gens.get(uid)
            ans = g["output"] if g and g["status"] == "ok" else ""
            rec = {"uid": uid, "answer": ans, **judge_one(by_uid[uid], ans, judge_model)}
            done[uid] = rec
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
    labels = [done[u]["label"] for u in meta["items"]]
    correct = [float(l == "CORRECT") for l in labels]
    res = {"run": run, "judge": judge_model, "n": len(labels), "counts": dict(Counter(labels)),
           "value": sum(correct) / len(correct), "ci95": bootstrap_ci(correct),
           "unparsed": sum(bool(done[u].get("unparsed")) for u in meta["items"])}
    (JUDGE_DIR / f"{run}__judge-{safe}.summary.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


def export_audit(run: str, judge_file: str, n: int, seed: int = 0):
    """Stratified sample (by judge label) for blind human labelling; judge labels are not shown."""
    rows = [json.loads(l) for l in (JUDGE_DIR / judge_file).open(encoding="utf-8")]
    by_uid = {i["uid"]: i for i in data.items("filing_qa")}
    rng = random.Random(seed)
    strata = {}
    for r in rows:
        strata.setdefault(r["label"], []).append(r)
    pick = []
    for lab in sorted(strata):
        g = sorted(strata[lab], key=lambda r: r["uid"])
        pick += rng.sample(g, min(len(g), max(1, round(n * len(g) / len(rows)))))
    rng.shuffle(pick)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIT_DIR / f"{run}.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["uid", "question", "reference_answer", "candidate_answer", "label_dev", "label_stavan"])
        for r in pick:
            it = by_uid[r["uid"]]
            w.writerow([r["uid"], it["input"]["question"], it["gold"]["answer"], r["answer"], "", ""])
    return path


def cohen_kappa(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(a) | set(b)) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def audit(labels_csv: str, judge_file: str) -> dict:
    """Human-human agreement, then judge vs the humans' consensus (rows where they agree)."""
    with open(labels_csv, encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["label_dev"].strip() and r["label_stavan"].strip()]
    judge = {json.loads(l)["uid"]: json.loads(l)["label"] for l in (JUDGE_DIR / judge_file).open(encoding="utf-8")}
    d = [r["label_dev"].strip().upper() for r in rows]
    s = [r["label_stavan"].strip().upper() for r in rows]
    cons = [(r["uid"], x) for r, x, y in zip(rows, d, s) if x == y]
    h = [x for _, x in cons]
    j = [judge[u] for u, _ in cons]
    pos = [(jj == "CORRECT", hh == "CORRECT") for jj, hh in zip(j, h)]
    tp = sum(a and b for a, b in pos)
    tn = sum((not a) and (not b) for a, b in pos)
    return {"n_labelled": len(rows), "human_agreement": sum(x == y for x, y in zip(d, s)) / len(rows),
            "human_kappa": cohen_kappa(d, s), "n_consensus": len(cons),
            "judge_agreement": sum(x == y for x, y in zip(j, h)) / len(cons), "judge_kappa": cohen_kappa(j, h),
            "judge_tpr_correct": tp / max(1, sum(b for _, b in pos)),
            "judge_tnr_correct": tn / max(1, sum(not b for _, b in pos)),
            "publish_threshold": 0.6}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    ap.add_argument("--judge")
    ap.add_argument("--export-audit")
    ap.add_argument("--judge-file")
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--audit")
    a = ap.parse_args()
    if a.audit:
        print(json.dumps(audit(a.audit, a.judge_file), indent=1))
    elif a.export_audit:
        print(export_audit(a.export_audit, a.judge_file, a.n))
    else:
        print(json.dumps(judge_run(a.run, a.judge), indent=1))


if __name__ == "__main__":
    main()
