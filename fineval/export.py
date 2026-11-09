"""Export everything the website shows into site/public/data/*.json (Phase 9).

    python -I -m fineval.export

The site renders only what is in these files. Reproduced scores come from results/scores and
results/judgements; published scores from reference/published.json, always labelled as such.
"""
import json

from .build import OUT as DATA
from .fetch import ROOT, load_manifest
from .sources.registry import SOURCES

SITE = ROOT / "site" / "public" / "data"
RESULTS = ROOT / "results"

TASK_INFO = {
    "concept_tagging": {"title": "XBRL concept tagging", "metric": "Accuracy (exact concept)",
                        "sources": ["FinTagging FinCL subset", "Regulations Challenge tag queries"]},
    "fact_extraction": {"title": "Fact extraction", "metric": "Micro F1 over (fact, type) pairs",
                        "sources": ["FinTagging FinNI subset"]},
    "financial_calc": {"title": "Financial calculation", "metric": "Accuracy (numeric match)",
                       "sources": ["XBRL-Agent formulas (Regulations Challenge math is a subset)"]},
    "filing_qa": {"title": "Filing QA", "metric": "Share judged correct",
                  "sources": ["FinanceBench open sample (XBRL-Agent and Regulations Challenge copies merged)"]},
}


def _read(p):
    return json.loads(p.read_text(encoding="utf-8"))


def reproduced_rows():
    rows = []
    for p in sorted((RESULTS / "scores").glob("*.json")) if (RESULTS / "scores").exists() else []:
        s = _read(p)
        if s["meta"]["task"] == "filing_qa" or not s.get("primary"):
            continue
        rows.append({"model": s["meta"]["model"].replace("ollama:", ""), "task": s["meta"]["task"],
                     "track": s["meta"]["track"], "n": s["primary"]["n"], "value": s["primary"]["value"],
                     "ci95": s["primary"]["ci95"], "metric": s["primary"]["primary_metric"],
                     "kind": "reproduced", "run": s["run"], "model_digest": s["meta"].get("model_digest"),
                     "seed": s["meta"]["seed"], "status": s["status"],
                     "by_subset": {k: (v["value"] if v else None) for k, v in s["by_subset"].items()}})
    for p in sorted((RESULTS / "judgements").glob("*.summary.json")) if (RESULTS / "judgements").exists() else []:
        s = _read(p)
        meta = _read(RESULTS / "generations" / f"{s['run']}.meta.json")
        rows.append({"model": meta["model"].replace("ollama:", ""), "task": "filing_qa", "track": meta["track"],
                     "n": s["n"], "value": s["value"], "ci95": s["ci95"], "metric": "correct", "kind": "reproduced",
                     "run": s["run"], "judge": s["judge"], "counts": s["counts"], "seed": meta["seed"],
                     "model_digest": meta.get("model_digest")})
    return rows


# (published block, metric) -> FinEval task, how the published set relates to ours, scale to [0, 1]
PUBLISHED_MAP = [
    ("fintagging_table6", "fincl_accuracy", "concept_tagging", "Full FinCL-eval v2 (261,457 items), embedding retrieval top-200; we run the released 500-item subset", "different item set", 1),
    ("fintagging_table6", "finni_f1", "fact_extraction", "Full FinNI-eval v2 (28,787 items); we run the released 200-item subset", "different item set", 1),
    ("financebench_table2", "correct", "filing_qa", "Same 150 questions, human-graded", "same items, human grading", 150),
    ("coling_table4", "xbrl_tag", "concept_tagging", "The 90 Regulations Challenge tag queries only, organisers' scorer", "same items as one subset", 1),
    ("coling_table4", "xbrl_math", "financial_calc", "The 90 Regulations Challenge math items only (a subset of our 1,000)", "subset of items", 1),
    ("coling_table4", "xbrl_domain_numeric", "filing_qa", "The 89 Regulations Challenge FinanceBench questions, organisers' scorer", "subset of items", 1),
]


SOURCE_NAME = {"fintagging_table6": "FinTagging", "financebench_table2": "FinanceBench",
               "coling_table4": "Regulations Challenge"}


def published_rows():
    pub = _read(ROOT / "reference" / "published.json")
    rows = []
    for block, metric, task, scope, relation, scale in PUBLISHED_MAP:
        b = pub[block]
        i = b["metrics"].index(metric)
        for model, vals in b["rows"].items():
            name, _, setting = model.partition(" | ")
            rows.append({"task": task, "model": name, "setting": setting or None, "value": vals[i] / scale,
                         "source_name": SOURCE_NAME[block],
                         "raw": vals[i], "metric": metric, "kind": "published", "scope": scope, "relation": relation,
                         "citation": b["citation"], "page": b.get("page"), "table": b.get("table")})
    return rows


def main():
    SITE.mkdir(parents=True, exist_ok=True)
    summary, overlap = _read(DATA / "summary.json"), _read(DATA / "overlap.json")
    m = load_manifest()
    datasets = {
        "summary": summary, "overlap": overlap, "conflicts": _read(DATA / "conflicts.json"),
        "sources": [{"key": k, "title": v["title"], "repo": v["repo"], "commit": v["commit"], "licence": v["licence"],
                     "files": sum(1 for x in m if x.startswith(k + "/"))} for k, v in SOURCES.items()],
    }
    retrieval = {p.stem: _read(p) for p in sorted((RESULTS / "retrieval").glob("*.json"))} \
        if (RESULTS / "retrieval").exists() else {}
    files = {"tasks.json": TASK_INFO, "datasets.json": datasets, "published.json": published_rows(),
             "reproduced.json": reproduced_rows(), "retrieval.json": retrieval}
    for name, obj in files.items():
        (SITE / name).write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")
    print("exported", ", ".join(f"{k} ({len(v) if hasattr(v, '__len__') else ''})" for k, v in files.items()))


if __name__ == "__main__":
    main()
