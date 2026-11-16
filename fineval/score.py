"""Score a generation file. Every planned item counts: missing or skipped items score 0.

    python -I -m fineval.score --run <run name>

Writes results/scores/<run>.json with per-item scores, task aggregates on primary items (and on
all items, as a sensitivity row), bootstrap 95% CIs and run health (parsed / skipped / truncated).
filing_qa is judge-scored: see fineval.judge.
"""
import argparse
import json
from collections import Counter

from . import data, scorers
from .fetch import ROOT
from .run import GEN, RESULTS
from .stats import bootstrap_ci

SCORES = RESULTS / "scores"
PRIMARY_KEY = {"concept_exact@v1": "exact", "numeric_match@v1": "final", "finni_pair_f1@v1": "strict_f1"}


def _ci(metric, rows):
    if metric == "finni_pair_f1@v1":
        return bootstrap_ci(rows, stat=lambda v: scorers.aggregate(metric, v)["strict_f1"])
    key = PRIMARY_KEY[metric]
    return bootstrap_ci([r[key] for r in rows])


def score_run(name: str) -> dict:
    meta = json.loads((GEN / f"{name}.meta.json").read_text(encoding="utf-8"))
    gens = {}
    for line in (GEN / f"{name}.jsonl").open(encoding="utf-8"):
        g = json.loads(line)
        gens[g["uid"]] = g
    by_uid = {i["uid"]: i for i in data.items(meta["task"])}
    items = [by_uid[u] for u in meta["items"]]
    metric = items[0]["metric"]
    per = []
    for it in items:
        g = gens.get(it["uid"])
        out = g["output"] if g and g["status"] == "ok" else ""
        per.append({"uid": it["uid"], "subset": it["subset"], "primary": it["primary"],
                    "status": g["status"] if g else "missing", **scorers.score(metric, out, it["gold"])})

    def block(rows):
        if not rows:
            return None
        agg = scorers.aggregate(metric, [{k: v for k, v in r.items() if k not in ("uid", "subset", "primary", "status")}
                                         for r in rows])
        return {"n": len(rows), "primary_metric": PRIMARY_KEY[metric], "value": agg[PRIMARY_KEY[metric]],
                "ci95": _ci(metric, rows), "variants": agg}

    prim = [r for r in per if r["primary"]]
    res = {"run": name, "meta": {k: v for k, v in meta.items() if k != "items"}, "metric": metric,
           "status": dict(Counter(r["status"] for r in per)),
           "primary": block(prim), "all_items": block(per),
           "by_subset": {s: block([r for r in prim if r["subset"] == s]) for s in sorted({r["subset"] for r in prim})},
           "items": per}
    SCORES.mkdir(parents=True, exist_ok=True)
    (SCORES / f"{name}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    r = score_run(ap.parse_args().run)
    print(json.dumps({k: r[k] for k in ("run", "status", "primary")}, indent=1))


if __name__ == "__main__":
    main()
