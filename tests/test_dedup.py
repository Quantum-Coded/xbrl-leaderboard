"""Phase 3 on synthetic records: what must and must not be joined."""
import random

from fineval.dedup import dedup


def rec(uid, text, gold, task="financial_calc", source="xbrl_agent", subset="formula", split="test", sid=None):
    field = {"terminology": "term", "fact_extraction": "context"}.get(task, "question")
    return {"uid": uid, "source": source, "subset": subset, "source_split": split, "source_id": sid or uid,
            "task": task, "input": {field: text}, "gold": gold}


def same(res, a, b):
    return res.cluster_of[a] == res.cluster_of[b]


def test_formatting_variants_join():
    rs = [rec("x:a", '3. "What is the NPV of $1,000 at 5%?"', {"value": 1.0}),
          rec("c:b", "what is the NPV of 1000 at 5%", {"value": 1.0}, source="coling", subset="math")]
    res = dedup(rs)
    assert same(res, "x:a", "c:b") and res.conflicts == []


def test_different_numbers_never_join():
    rs = [rec("x:a", "Cash inflows of $6,000 for 4 years at 8%. NPV?", {"value": 1.0}),
          rec("c:b", "Cash inflows of $6,000 for 5 years at 8%. NPV?", {"value": 2.0}, source="coling", subset="math")]
    assert not same(dedup(rs), "x:a", "c:b")


def test_one_word_term_variants_never_join():
    rs = [rec("x:a", "Due from Related Parties, Current", {"definition": "a"}, task="terminology", subset="t"),
          rec("c:b", "Due to Related Parties, Current", {"definition": "b"}, task="terminology", source="coling", subset="t"),
          rec("c:c", "Assets, Noncurrent", {"definition": "c"}, task="terminology", source="coling", subset="t"),
          rec("x:d", "Assets, Current", {"definition": "d"}, task="terminology", subset="t")]
    res = dedup(rs)
    assert len(set(res.cluster_of.values())) == 4


def test_same_financebench_id_joins_despite_text_edits():
    rs = [rec("f:a", "What is 3M's FY2018 capex?", {"answer": "$1577.00"}, task="filing_qa", source="financebench",
              subset="open", sid="financebench_id_03029"),
          rec("x:b", "What is the FY2018 capex for 3M?", {"answer": "1577"}, task="filing_qa", subset="financebench",
              sid="financebench_id_03029")]
    res = dedup(rs)
    assert same(res, "f:a", "x:b") and res.conflicts == []
    assert res.clusters[res.cluster_of["f:a"]]["representative"] == "f:a"   # original publisher wins


def test_tasks_never_mix():
    rs = [rec("x:a", "Revenue", {"definition": "a"}, task="terminology", subset="t"),
          rec("c:b", "Revenue", {"value": 1.0}, source="coling", subset="math")]
    assert not same(dedup(rs), "x:a", "c:b")


def test_conflict_detected():
    rs = [rec("f:a", "Same question?", {"answer": "No, negative"}, task="filing_qa", source="financebench", subset="open"),
          rec("c:b", "Same question?", {"answer": "Yes, positive"}, task="filing_qa", source="coling", subset="d")]
    res = dedup(rs)
    assert len(res.conflicts) == 1 and res.conflicts[0]["kind"] == "same_input_different_gold"


def test_order_invariance():
    rs = [rec(f"x:{i}", f"Question number {i % 7} about margins", {"value": float(i % 7)},
              source=["xbrl_agent", "coling"][i % 2], subset=["formula", "math"][i % 2]) for i in range(40)]
    base = dedup(rs).cluster_of
    for seed in range(3):
        shuffled = rs[:]
        random.Random(seed).shuffle(shuffled)
        assert dedup(shuffled).cluster_of == base


def test_review_queue_and_human_decision():
    a = "Does Boeing have an improving gross margin profile as of FY2022? Answer using the income statement."
    b = "Does Boeing have an improving gross margins profile as of FY2022? Answer using the income statement only."
    rs = [rec("f:a", a, {"answer": "x"}, task="filing_qa", source="financebench", subset="open"),
          rec("c:b", b, {"answer": "x"}, task="filing_qa", source="coling", subset="d")]
    res = dedup(rs)
    assert not same(res, "f:a", "c:b") and len(res.review) == 1
    assert same(dedup(rs, {("c:b", "f:a"): "join"}), "f:a", "c:b")
