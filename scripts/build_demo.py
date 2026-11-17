"""Build the XBRL Leaderboard page data from raw generations, and audit it against stored scores.

Every number on the page comes from here. The script rescores each run from its generations
(independently of fineval.score), checks the result equals the stored score file, and fails loudly on
any mismatch. Latency and memory are copied from the profile files, one block per machine, never mixed.

Usage: PYTHONUTF8=1 python scripts/build_demo.py
Writes demo/data.js (loaded by demo/index.html) and results/audit/demo_numbers.json
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fineval import scorers, stats  # noqa: E402

# (run key, name on the page, parameters in billions), ordered by size
MODELS = [("qwen2.5-1.5b", "Qwen2.5-1.5B", 1.5), ("gemma2-2b", "Gemma-2-2B", 2.6), ("qwen2.5-3b", "Qwen2.5-3B", 3.1),
          ("llama3.2-3b", "Llama-3.2-3B", 3.2), ("qwen2.5-7b", "Qwen2.5-7B", 7.6), ("mistral-7b", "Mistral-7B", 7.2),
          ("llama3.1-8b", "Llama-3.1-8B", 8.0)]
# (run key, label, short label, oracle). `tools` filters the search to the item's given type, which equals the
# gold concept's type on every item (checked below), so it is an oracle diagnostic. `tools_numeric` restricts the
# search to a fixed list of numeric XBRL types (fineval/tools.py NUMERIC_TYPES); `tools_noorac` uses no type.
CONDITIONS = [("closed", "No tools", "No tools", False),
              ("tools_noorac", "Tag search, no type", "Search", False),
              ("tools_numeric", "Tag search, numeric types only", "Search + numeric", False),
              ("tools", "Tag search, given item type (oracle diagnostic)", "Search + oracle type", True)]
PROFILED = ("closed", "tools_noorac", "tools")
MACHINES = [("windows", ROOT / "results", ROOT / "results/profile/rtx-4050-laptop-gpu"),
            ("mac", ROOT / "results/mac/m4", ROOT / "results/mac/m4/profile/m4")]
# calculation: every model with both runs saved
CALC_MODELS = [m for m in MODELS if all((ROOT / f"results/scores/{m[0]}__financial_calc__{t}__s0.json").exists()
                                        for t in ("closed", "tools"))]
SUBSET = "fincl_subset"


def load_jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def check_stored(run, stored_block, xs):
    acc = sum(xs) / len(xs)
    lo, hi = stats.bootstrap_ci(xs)
    assert stored_block["n"] == len(xs), (run, stored_block["n"], len(xs))
    assert abs(stored_block["value"] - acc) < 1e-12, (run, stored_block["value"], acc)
    assert abs(stored_block["ci95"][0] - lo) < 1e-12 and abs(stored_block["ci95"][1] - hi) < 1e-12, (run, lo, hi)
    return acc, lo, hi


def tagging_runs(res_dir, fincl, audit, machine):
    runs, per_item = [], {}
    for mkey, mname, _ in MODELS:
        for ckey, cname, _, oracle in CONDITIONS:
            run = f"{mkey}__concept_tagging__{ckey}__s0"
            gpath = res_dir / f"generations/{run}.jsonl"
            if not gpath.exists():
                continue
            gens = {g["uid"]: g for g in load_jsonl(gpath)}
            meta = json.loads((res_dir / f"generations/{run}.meta.json").read_text(encoding="utf-8"))
            stored = json.loads((res_dir / f"scores/{run}.json").read_text(encoding="utf-8"))
            exact, rows = [], []
            for it in fincl:
                g = gens.get(it["uid"])
                out = g["output"] if g and g["status"] == "ok" else ""
                e = scorers.concept_exact(out, it["gold"])["exact"]
                exact.append(e)
                cands = (g or {}).get("tool_log", {}).get("candidates") if ckey != "closed" else None
                c = None if cands is None else float(any(x in cands for x in it["gold"]["concepts"]))
                rows.append({"uid": it["uid"], "pred": scorers.parse_concept(out), "exact": e, "covered": c,
                             "status": g["status"] if g else "missing"})
            per_item[run] = rows
            acc, lo, hi = check_stored(run, stored["by_subset"][SUBSET], exact)
            r = {"machine": machine, "run": run, "model_key": mkey, "model": mname, "model_tag": meta["model"],
                 "model_digest": meta["model_digest"][:12], "runtime": meta.get("runtime"), "condition": ckey,
                 "condition_label": cname, "tools": ckey != "closed", "oracle": oracle, "n": len(exact),
                 "correct": int(sum(exact)), "accuracy": round(100 * acc, 1),
                 "ci95": [round(100 * lo, 1), round(100 * hi, 1)],
                 "parsed": sum(1 for x in rows if x["pred"]), "status": dict(Counter(x["status"] for x in rows))}
            cov = [x["covered"] for x in rows if x["covered"] is not None]
            if cov:
                both = sum(1 for x in rows if x["covered"] and x["exact"])
                r.update(coverage=round(100 * sum(cov) / len(cov), 1), covered_items=int(sum(cov)),
                         selected_covered_items=both, selected_if_covered=round(100 * both / sum(cov), 1),
                         correct_outside_candidates=sum(1 for x in rows if x["exact"] and not x["covered"]))
            runs.append(r)
            audit.append(f"[{machine}] {run}: rescored {r['correct']}/{r['n']} = {r['accuracy']}% CI {r['ci95']} == stored")
    return runs, per_item


def cost_block(prof_dir):
    rows, info = [], None
    for mkey, mname, _ in MODELS:
        for ckey in PROFILED:
            p = prof_dir / f"{mkey}__{ckey}__n100.json"
            if not p.exists():
                continue
            d = json.loads(p.read_text(encoding="utf-8"))
            assert d["on_ac_power"] is not False, (p, "profile made on battery")
            s, pk = d["summary"], d["summary"]["memory_peak_mib"]
            m = d["machine"]
            info = info or {"name": d["machine_name"], "hardware": m.get("gpu", "").split(",")[0] or m.get("chip"),
                            "chip": m.get("chip") or m.get("cpu"), "ram_gb": m.get("ram_gb"), "os": m["os"].split("-")[0],
                            "ollama": d["ollama_version"]}
            rows.append({"model_key": mkey, "model": mname, "condition": ckey, "n": d["n"],
                         "latency_median_s": round(s["latency_median_s"], 2), "latency_p90_s": round(s["latency_p90_s"], 2),
                         "prompt_tokens_median": int(s["prompt_tokens_median"]),
                         "model_loaded_mib": pk["ollama_size_mib"],
                         "on_gpu_mib": pk["ollama_size_vram_mib"],
                         "gpu_peak_mib": s.get("gpu_peak_minus_baseline_mib"),
                         "process_peak_mib": pk.get("ollama_rss_mib") or None})
    return {"machine": info, "rows": rows}


def calc_runs(audit):
    test = {i["uid"]: i for i in load_jsonl(ROOT / "data/v1/test/financial_calc.jsonl")}
    items = [i for i in test.values() if i["primary"]]
    runs = []
    for mkey, mname, _ in CALC_MODELS:
        for ckey, label in (("closed", "No tools"), ("tools", "Formula lookup + calculator")):
            run = f"{mkey}__financial_calc__{ckey}__s0"
            gens = {g["uid"]: g for g in load_jsonl(ROOT / f"results/generations/{run}.jsonl")}
            meta = json.loads((ROOT / f"results/generations/{run}.meta.json").read_text(encoding="utf-8"))
            stored = json.loads((ROOT / f"results/scores/{run}.json").read_text(encoding="utf-8"))
            xs = [scorers.numeric_match(gens[i["uid"]]["output"] if gens[i["uid"]]["status"] == "ok" else "",
                                        i["gold"])["final"] for i in items]
            acc, lo, hi = check_stored(run, stored["primary"], xs)
            r = {"run": run, "model": mname, "condition": ckey, "condition_label": label, "n": len(xs),
                 "correct": int(sum(xs)), "accuracy": round(100 * acc, 1), "ci95": [round(100 * lo, 1), round(100 * hi, 1)],
                 "runtime": meta.get("runtime")}
            if ckey == "tools":
                r["formula_found"] = sum(1 for i in items if (gens[i["uid"]]["tool_log"] or {}).get("formula") and
                                         gens[i["uid"]]["tool_log"]["formula"]["name"] ==
                                         i["input"]["formula_name"].strip().lower())
            runs.append(r)
            audit.append(f"[calc] {run}: rescored {r['correct']}/{r['n']} = {r['accuracy']}% == stored")
    return {"name": "Financial calculation (XBRL-Agent formulas)", "items": len(items),
            "formulas": len({i["input"]["formula_name"].strip().lower() for i in items}),
            "metric": "A number in the final part of the answer is within 1% of the correct value (numeric_match@v1)",
            "runs": runs}


def main():
    test = {i["uid"]: i for i in load_jsonl(ROOT / "data/v1/test/concept_tagging.jsonl")}
    fincl_all = [i for i in test.values() if i["subset"] == SUBSET]
    fincl = [i for i in fincl_all if i["primary"]]
    summary = json.loads((ROOT / "data/v1/summary.json").read_text(encoding="utf-8"))
    tax = load_jsonl(ROOT / "data/raw/fintagging/taxonomy/us_gaap_2024_BM25.jsonl")

    # the oracle claim, checked on every scored item: given item type == type of each gold concept
    ttype = {"us-gaap:" + r["us_gaap_tag"]: r["entity_type"] for r in tax}
    type_equal = sum(all(ttype.get(c) == i["input"]["entity_type"] for c in i["gold"]["concepts"]) for i in fincl)
    assert type_equal == len(fincl), ("given type is not always the gold type", type_equal, len(fincl))

    audit = []
    runs, per_item = tagging_runs(ROOT / "results", fincl, audit, "windows")
    mac_runs, _ = tagging_runs(ROOT / "results/mac/m4", fincl, audit, "mac")
    # every model must have every condition on Windows, so the main table has no gaps
    for mkey, _, _ in MODELS:
        have = {r["condition"] for r in runs if r["model_key"] == mkey}
        assert have == {c[0] for c in CONDITIONS}, (mkey, have)

    # paired difference, oracle-free search minus no tools, per model
    paired = {}
    for mkey, mname, _ in MODELS:
        a = [x["exact"] for x in per_item[f"{mkey}__concept_tagging__closed__s0"]]
        b = [x["exact"] for x in per_item[f"{mkey}__concept_tagging__tools_noorac__s0"]]
        p = stats.paired_bootstrap(a, b)
        paired[mname] = {"diff": round(100 * p["diff"], 1), "ci95": [round(100 * p["ci"][0], 1), round(100 * p["ci"][1], 1)]}

    # worked examples from Qwen2.5-7B with oracle tag search: one pass, one fail where the gold was in the list
    q = per_item["qwen2.5-7b__concept_tagging__tools__s0"]

    def example(row, verdict, why):
        it = test[row["uid"]]
        inp = it["input"]
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
                 "taxonomy_concepts": len(tax), "metric": "Exact match on the US-GAAP concept (concept_exact@v1)",
                 "ci": "95% bootstrap over items (2,000 resamples, seed 0)",
                 "decoding": "greedy, 4-bit GGUF via Ollama, seed 0", "candidates": 100},
        "models": [{"key": k, "name": n, "params_b": p} for k, n, p in MODELS],
        "conditions": [{"key": k, "label": l, "short": s, "oracle": o} for k, l, s, o in CONDITIONS],
        "runs": runs, "mac_runs": mac_runs,
        "cost": {name: cost_block(prof) for name, _, prof in MACHINES},
        "calc": calc_runs(audit),
        "paired_search_minus_closed": paired, "examples": examples,
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
    for r in runs:
        print(f"{r['model']:14s} {r['condition']:14s} {r['accuracy']:5.1f}% {r['ci95']} cov={r.get('coverage')} "
              f"sel={r.get('selected_if_covered')} parsed={r['parsed']}/{r['n']}")
    for name, block in data["cost"].items():
        print(name, block["machine"], len(block["rows"]), "profile rows")


if __name__ == "__main__":
    main()
