"""Retrieval ceilings for the tool-assisted track, computed without any LLM.

    python -I -m fineval.retrieval_eval [--filings]

taxonomy: share of concept-tagging items whose gold concept is in the BM25 top-k (Acc@k).
          No reranker can beat Acc@k, so it bounds tool-assisted tagging accuracy.
filings:  share of FinanceBench questions where a gold evidence page is in the top-k pages.
"""
import argparse
import json

from . import data, tools
from .fetch import ROOT
from .stats import bootstrap_ci

OUT = ROOT / "results" / "retrieval"
KS = (1, 5, 10, 20, 50, 100, 200)


def taxonomy():
    res = {}
    for subset, qfn, typed in (("fincl_subset", tools.fincl_query_text, True), ("tag_query", tools.tag_query_text, False)):
        items = [i for i in data.items("concept_tagging") if i["subset"] == subset and i["primary"]]
        for use_type in ((False, True) if typed else (False,)):
            hits = {k: [] for k in KS}
            for it in items:
                ranked = tools.taxonomy_search(qfn(it["input"]), k=max(KS),
                                               entity_type=it["input"]["entity_type"] if use_type else None)
                gold = set(it["gold"]["concepts"])
                for k in KS:
                    hits[k].append(float(bool(gold & set(ranked[:k]))))
            name = f"{subset}{'+type' if use_type else ''}"
            res[name] = {"n": len(items), **{f"acc@{k}": {"value": sum(v) / len(v), "ci95": bootstrap_ci(v)}
                                             for k, v in hits.items()}}
            print(name, len(items), {k: round(sum(v) / len(v), 3) for k, v in hits.items()}, flush=True)
    return res


def filings():
    items = data.items("filing_qa")
    res, hits = {}, {k: [] for k in (1, 3, 5, 10)}
    for it in items:
        gold_pages = {e["page"] for e in it["gold"].get("evidence", []) if e.get("page") is not None}
        ranked = [p for p, _ in tools.filing_search(it["input"]["doc_name"], it["input"]["question"], k=10)]
        for k in hits:
            hits[k].append(float(bool(gold_pages & set(ranked[:k]))))
    res["financebench_open"] = {"n": len(items), **{f"recall@{k}": {"value": sum(v) / len(v), "ci95": bootstrap_ci(v)}
                                                    for k, v in hits.items()}}
    print(res, flush=True)
    return res


def formulas():
    from .prompts import formula_search
    hits = []
    for it in data.items("financial_calc"):
        f = formula_search(it["input"]["question"])
        hits.append(float(bool(f) and f["name"] == it["input"]["formula_name"].strip().lower()))
    res = {"xbrl_agent_formula": {"n": len(hits), "acc@1": {"value": sum(hits) / len(hits), "ci95": bootstrap_ci(hits)}}}
    print(res, flush=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--filings", action="store_true")
    ap.add_argument("--formulas", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    name, res = (("filings", filings()) if args.filings else ("formulas", formulas()) if args.formulas
                 else ("taxonomy", taxonomy()))
    (OUT / f"{name}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
