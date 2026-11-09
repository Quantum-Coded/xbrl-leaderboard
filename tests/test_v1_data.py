"""Phase 3-4 on the built benchmark (run `python -I -m fineval.build` first)."""
import json
from collections import defaultdict

import pytest

from fineval import data
from fineval.build import OUT

TASKS = ("concept_tagging", "fact_extraction", "filing_qa", "financial_calc", "terminology")


def _jsonl(p):
    return [json.loads(l) for l in p.open(encoding="utf-8")]


@pytest.fixture(scope="module")
def built():
    if not (OUT / "summary.json").exists():
        pytest.skip("run python -I -m fineval.build first")
    items = [it for sp in ("test", "validation", "train") for t in TASKS
             for it in (_jsonl(OUT / sp / f"{t}.jsonl") if (OUT / sp / f"{t}.jsonl").exists() else [])]
    clusters = {c["cluster_id"]: c for c in _jsonl(OUT / "clusters.jsonl")}
    return items, clusters


def _contained(clusters, member_prefix, target_prefix):
    hits = total = 0
    for c in clusters.values():
        mine = [u for u in c["members"] if u.startswith(member_prefix)]
        total += len(mine)
        if any(u.startswith(target_prefix) for u in c["members"]):
            hits += len(mine)
    return hits, total


def test_known_overlaps_recovered(built):
    _, cl = built
    assert _contained(cl, "coling:terminology:", "xbrl_agent:terminology:") == (445, 445)
    assert _contained(cl, "coling:domain_numeric:", "financebench:open:") == (99, 99)
    assert _contained(cl, "xbrl_agent:financebench:", "financebench:open:") == (149, 149)
    assert _contained(cl, "coling:math:test:", "xbrl_agent:formula:") == (90, 90)
    assert _contained(cl, "coling:math:validation:", "xbrl_agent:formula:") == (100, 100)


def test_one_item_per_cluster_and_no_cross_split_leak(built):
    items, clusters = built
    seen = {}
    for it in items:
        assert it["cluster_id"] not in seen, f"cluster {it['cluster_id']} appears twice"
        seen[it["cluster_id"]] = it["split"]
    every_uid = defaultdict(int)
    for it in items:
        for u in [it["uid"], *it["also_in"]]:
            every_uid[u] += 1
    assert max(every_uid.values()) == 1


def test_no_filing_leak_into_train(built):
    items, _ = built
    test_filings = {i["filing_key"] for i in items if i["split"] == "test" and i["filing_key"]}
    assert not {i["filing_key"] for i in items if i["split"] == "train" and i["filing_key"]} & test_filings
    for i in items:
        if i["split"] == "validation" and i["filing_key"] in test_filings:
            assert "filing_in_test" in i["flags"]


def test_train_has_no_conflicts_or_risky_items(built):
    items, _ = built
    assert not [i for i in items if i["split"] == "train" and i["flags"]]
    dropped = json.loads((OUT / "dropped.json").read_text(encoding="utf-8"))
    assert {d["reason"] for d in dropped} <= {"conflicting_gold", "near_duplicate_of_eval_item", "contains_test_text"}


def test_fewshot_pool_respects_filing_and_cluster():
    for it in data.items("concept_tagging", "test"):
        for ex in data.fewshot_pool("concept_tagging", it, k=3):
            assert ex["cluster_id"] != it["cluster_id"]
            assert not (it["filing_key"] and ex["filing_key"] == it["filing_key"])


def test_ambiguous_items_excluded_from_primary(built):
    items, _ = built
    for i in items:
        assert i["primary"] == ("ambiguous" not in i["flags"])
    amb = [i for i in items if i["task"] == "concept_tagging" and "ambiguous" in i["flags"]]
    assert len(amb) == 7 and all(len(i["gold"]["concepts"]) >= 2 for i in amb)


def test_summary_matches_files(built):
    items, _ = built
    s = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
    counts = defaultdict(int)
    for i in items:
        counts[f"{i['task']}:{i['split']}"] += 1
    assert dict(counts) == s["items"]


def test_sample_is_fixed_and_stratified():
    a = data.sample("concept_tagging", 100, seed=0)
    assert [r["uid"] for r in a] == [r["uid"] for r in data.sample("concept_tagging", 100, seed=0)]
    subsets = {r["subset"] for r in a}
    assert subsets == {"fincl_subset", "tag_query"}
