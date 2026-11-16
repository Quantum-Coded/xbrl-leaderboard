"""Coverage of BM25 taxonomy search on FinCL test items under different item-type conditions.

Coverage@k = share of scored FinCL items whose gold concept is among the top-k candidates.
Conditions:
  none        no type filter
  numeric     restricted to numeric XBRL item types, fixed in advance from the XBRL 2.1 and DTR numeric
              types present in the taxonomy (NUMERIC_TYPES below; not derived from test items)
  monetary    always assume monetaryItemType (majority guess)
  heuristic   type guessed from the row text (% / per share / shares cues, else monetary)
  given       the item's own entity_type (oracle: it always equals the gold concept's type)
  soft_given  BM25 analogue of FinTagging's soft type match: the type's tokens are appended to every
              concept's text and to the query, with no filter (oracle: uses the given type)
Results are split into monetary and non-monetary items.

Usage: PYTHONUTF8=1 python scripts/type_filter_coverage.py
Writes results/retrieval/type_filter_coverage.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fineval import tools  # noqa: E402

KS = (100, 200)
NUMERIC_TYPES = tools.NUMERIC_TYPES  # XBRL 2.1 + DTR numeric item types (fixed list, see fineval/tools.py)


def guess_type(row: str) -> str:
    r = row.lower()
    if "%" in r or "percent" in r or "rate" in r:
        return "percentItemType"
    if "per share" in r or "per common share" in r:
        return "perShareItemType"
    if "shares" in r and "$" not in r:
        return "sharesItemType"
    return "monetaryItemType"


def main():
    items = [json.loads(l) for l in open(ROOT / "data/v1/test/concept_tagging.jsonl", encoding="utf-8")]
    items = [i for i in items if i["subset"] == "fincl_subset" and i["primary"]]
    rows, _ = tools._taxonomy()
    ttype = {r["us_gaap_tag"]: r["entity_type"] for r in rows}
    numeric = sorted(NUMERIC_TYPES)
    from rank_bm25 import BM25Okapi
    soft_bm = BM25Okapi([tools.tokens(r["text"]) + tools.tokens(r["us_gaap_tag"]) + tools.tokens(r["entity_type"])
                         for r in rows])

    def soft_search(q, t, k):
        sc = soft_bm.get_scores(tools.tokens(q) + tools.tokens(t))
        idx = sorted(range(len(rows)), key=lambda i: (-sc[i], rows[i]["us_gaap_tag"]))[:k]
        return ["us-gaap:" + rows[i]["us_gaap_tag"] for i in idx]
    kmax = max(KS)

    def ranked(it, cond):
        q = tools.fincl_query_text(it["input"])
        if cond == "none":
            return tools.taxonomy_search(q, k=kmax)
        if cond == "numeric":
            pool = tools.taxonomy_search(q, k=len(rows))
            return [c for c in pool if ttype[c[len("us-gaap:"):]] in numeric][:kmax]
        if cond == "soft_given":
            return soft_search(q, it["input"]["entity_type"], kmax)
        t = {"monetary": "monetaryItemType", "given": it["input"]["entity_type"],
             "heuristic": guess_type(q)}[cond]
        return tools.taxonomy_search(q, k=kmax, entity_type=t)

    groups = {"all": items,
              "monetary": [i for i in items if i["input"]["entity_type"] == "monetaryItemType"],
              "non_monetary": [i for i in items if i["input"]["entity_type"] != "monetaryItemType"]}
    out = {"n": {g: len(v) for g, v in groups.items()}, "numeric_types": numeric,
           "heuristic_type_accuracy": sum(guess_type(tools.fincl_query_text(i["input"])) == i["input"]["entity_type"]
                                          for i in items) / len(items),
           "monetary_guess_accuracy": len(groups["monetary"]) / len(items),
           "coverage": {}}
    for cond in ("none", "numeric", "monetary", "heuristic", "soft_given", "given"):
        cands = {i["uid"]: ranked(i, cond) for i in items}
        out["coverage"][cond] = {
            f"@{k}": {g: round(100 * sum(any(c in cands[i["uid"]][:k] for c in i["gold"]["concepts"]) for i in v) / len(v), 1)
                      for g, v in groups.items()}
            for k in KS}
        print(cond, out["coverage"][cond])
    dest = ROOT / "results/retrieval/type_filter_coverage.json"
    dest.write_text(json.dumps(out, indent=2))
    print("type guess accuracy", out["heuristic_type_accuracy"], "| always monetary", out["monetary_guess_accuracy"])
    print("wrote", dest)


if __name__ == "__main__":
    main()
