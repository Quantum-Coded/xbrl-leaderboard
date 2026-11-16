"""Build the XBRL Leaderboard demo data from raw generations, and audit it against stored scores.

Every number on the demo page and in the proposal comes from here. The script rescores each run
from its generations (independently of fineval.score), checks the result equals the stored score
file, and fails loudly on any mismatch.

Usage: PYTHONUTF8=1 python scripts/build_demo.py
Writes demo/data.js (loaded by demo/index.html) and results/audit/demo_numbers.json
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fineval import scorers, stats  # noqa: E402

MODELS = [("qwen2.5-7b", "Qwen2.5-7B-Instruct"), ("llama3.1-8b", "Llama-3.1-8B-Instruct"),
          ("qwen2.5-3b", "Qwen2.5-3B-Instruct")]
# (run key, label on the page, uses the oracle item type). The `tools` runs filter the search to the item's
# given type (fineval/prompts.py), which equals the gold concept's type, so they are an oracle diagnostic.
TRACKS = [("closed", "No tools", False), ("tools", "Tag search (given item type: oracle diagnostic)", True)]
SUBSET = "fincl_subset"


def load_jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def main():
    test = {i["uid"]: i for i in load_jsonl(ROOT / "data/v1/test/concept_tagging.jsonl")}
    fincl_all = [i for i in test.values() if i["subset"] == SUBSET]
    fincl = [i for i in fincl_all if i["primary"]]
    summary = json.loads((ROOT / "data/v1/summary.json").read_text(encoding="utf-8"))
    n_taxonomy = sum(1 for l in open(ROOT / "data/raw/fintagging/taxonomy/us_gaap_2024_BM25.jsonl", encoding="utf-8")
                     if l.strip())

    # the oracle claim, checked on every scored item: given item type == type of each gold concept
    ttype = {"us-gaap:" + json.loads(l)["us_gaap_tag"]: json.loads(l)["entity_type"]
             for l in open(ROOT / "data/raw/fintagging/taxonomy/us_gaap_2024_BM25.jsonl", encoding="utf-8") if l.strip()}
    type_equal = sum(all(ttype.get(c) == i["input"]["entity_type"] for c in i["gold"]["concepts"]) for i in fincl)
    assert type_equal == len(fincl), ("given type is not always the gold type", type_equal, len(fincl))

    audit, runs, per_item = [], [], {}
    for mkey, mname in MODELS:
        for tkey, tname, oracle in TRACKS:
            run = f"{mkey}__concept_tagging__{tkey}__s0"
            gens = {g["uid"]: g for g in load_jsonl(ROOT / f"results/generations/{run}.jsonl")}
            meta = json.loads((ROOT / f"results/generations/{run}.meta.json").read_text(encoding="utf-8"))
            stored = json.loads((ROOT / f"results/scores/{run}.json").read_text(encoding="utf-8"))
            exact, cov, rows = [], [], []
            for it in fincl:
                g = gens.get(it["uid"])
                out = g["output"] if g and g["status"] == "ok" else ""
                e = scorers.concept_exact(out, it["gold"])["exact"]
                exact.append(e)
                cands = (g or {}).get("tool_log", {}).get("candidates") if tkey != "closed" else None
                c = None if cands is None else float(any(x in cands for x in it["gold"]["concepts"]))
                if c is not None:
                    cov.append(c)
                rows.append({"uid": it["uid"], "pred": scorers.parse_concept(out), "exact": e, "covered": c,
                             "status": g["status"] if g else "missing"})
            per_item[run] = rows
            acc = sum(exact) / len(exact)
            lo, hi = stats.bootstrap_ci(exact)
            s = stored["by_subset"][SUBSET]
            assert s["n"] == len(exact), (run, s["n"], len(exact))
            assert abs(s["value"] - acc) < 1e-12, (run, s["value"], acc)
            assert abs(s["ci95"][0] - lo) < 1e-12 and abs(s["ci95"][1] - hi) < 1e-12, (run, s["ci95"], lo, hi)
            r = {"run": run, "model": mname, "model_tag": meta["model"], "model_digest": meta["model_digest"][:12],
                 "runtime": meta.get("runtime"), "track": tname, "condition": tkey, "tools": tkey != "closed",
                 "oracle": oracle, "n": len(exact),
                 "correct": int(sum(exact)), "accuracy": round(100 * acc, 1),
                 "ci95": [round(100 * lo, 1), round(100 * hi, 1)],
                 "status": dict(Counter(x["status"] for x in rows))}
            if cov:
                both = sum(1 for x in rows if x["covered"] and x["exact"])
                r["coverage"] = round(100 * sum(cov) / len(cov), 1)
                r["covered_items"] = int(sum(cov))
                r["selected_covered_items"] = both
                r["selected_if_covered"] = round(100 * both / sum(cov), 1)
                r["correct_outside_candidates"] = sum(1 for x in rows if x["exact"] and not x["covered"])
            runs.append(r)
            audit.append(f"{run}: rescored {r['correct']}/{r['n']} = {r['accuracy']}% "
                         f"CI {r['ci95']} == stored score file")

    # paired difference, tools minus no-tools, per model
    paired = {}
    for mkey, mname in MODELS:
        a = [x["exact"] for x in per_item[f"{mkey}__concept_tagging__closed__s0"]]
        b = [x["exact"] for x in per_item[f"{mkey}__concept_tagging__tools__s0"]]
        p = stats.paired_bootstrap(a, b)
        paired[mname] = {"diff": round(100 * p["diff"], 1), "ci95": [round(100 * p["ci"][0], 1), round(100 * p["ci"][1], 1)]}

    # worked examples from Qwen2.5-7B with tag search: one pass, one fail where the gold was in the list
    q = per_item["qwen2.5-7b__concept_tagging__tools__s0"]

    def example(row, verdict, why):
        it = test[row["uid"]]
        inp = it["input"]
        import re
        m = re.search(r"<context>(.*?)</context>", inp["query"], re.S)
        return {"uid": row["uid"], "row": (m.group(1) if m else "").strip(), "value": inp["entity"],
                "type": inp["entity_type"], "gold": it["gold"]["concepts"][0], "pred": row["pred"],
                "verdict": verdict, "why": why}

    passed = next(r for r in q if r["exact"] == 1.0)
    failed = next(r for r in q if r["exact"] == 0.0 and r["covered"] == 1.0 and r["pred"])
    examples = [example(passed, "pass", "Exact match with the gold US-GAAP concept."),
                example(failed, "fail", "The gold concept was in the 100 candidates, but the model chose a different one.")]

    data = {
        "task": {"name": "Concept linking (FinCL)", "source": "FinTagging public release (GitHub subset)",
                 "released": 500, "after_dedup": len(fincl_all), "scored": len(fincl),
                 "excluded_conflicts": summary["flags"]["concept_tagging:ambiguous"],
                 "table_rows": sum(1 for i in fincl if i["input"]["category"] == "table"),
                 "taxonomy_concepts": n_taxonomy, "metric": "Exact match on the US-GAAP concept (concept_exact@v1)",
                 "ci": "95% bootstrap over items (2,000 resamples, seed 0)",
                 "decoding": "greedy, 4-bit GGUF via Ollama, seed 0"},
        "runs": runs, "paired_tools_minus_closed": paired, "examples": examples,
        "oracle_check": {"items": len(fincl), "given_type_equals_gold_type": type_equal},
        "dedup": {"records": summary["records_loaded"], "unique": summary["clusters"],
                  "text_joins": summary["joins"]["exact_text"], "id_joins": summary["joins"]["same_source_id"],
                  "review_pairs": summary["review_pairs"]},
        # FinTagging arXiv:2505.20650v5, Table 8, FinCL column (checked against the arXiv HTML on 2026-11-15)
        "published": [{"system": "GPT-4o", "score": 18.3}, {"system": "Llama-3.1-8B-Instruct", "score": 9.1}],
        "published_note": "FinTagging paper (arXiv:2505.20650v5), Table 8, FinCL accuracy. Full gated test set and "
                          "their own retriever, so not directly comparable with our runs on the public subset.",
    }
    (ROOT / "demo").mkdir(exist_ok=True)
    (ROOT / "demo/data.js").write_text("window.DEMO_DATA = " + json.dumps(data, indent=1) + ";\n", encoding="utf-8")
    (ROOT / "results/audit").mkdir(parents=True, exist_ok=True)
    (ROOT / "results/audit/demo_numbers.json").write_text(json.dumps({"checks": audit, **data}, indent=1), encoding="utf-8")
    print("\n".join(audit))
    print(json.dumps({k: data[k] for k in ("task", "paired_tools_minus_closed", "dedup")}, indent=1))
    for r in runs:
        print(r["model"], r["track"], r["accuracy"], r["ci95"], r.get("coverage"), r.get("selected_if_covered"),
              r.get("correct_outside_candidates"), r["status"])
    print(json.dumps(examples, indent=1))


if __name__ == "__main__":
    main()
