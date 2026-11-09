import pytest

from fineval import tools


@pytest.mark.parametrize("expr,val", [("1+2*3", 7), ("sum(6000/(1.08)**t for t in range(1,5))", 19872.76),
                                      ("sqrt(16)", 4), ("-(3)", -3), ("round(2.345, 2)", 2.35)])
def test_safe_eval_ok(expr, val):
    assert tools.safe_eval(expr) == pytest.approx(val, abs=0.01)


@pytest.mark.parametrize("expr", ["__import__('os')", "open('x')", "x + 1", "'a' * 3", "(lambda: 1)()",
                                  "[].__class__", "9 ** 99999"])
def test_safe_eval_rejects(expr):
    with pytest.raises((ValueError, SyntaxError)):
        tools.safe_eval(expr)


def test_taxonomy_search_finds_obvious_concepts():
    assert "us-gaap:AccountsReceivableNetCurrent" in tools.taxonomy_search("Accounts Receivable Net Current", k=5)
    hits = tools.taxonomy_search("Goodwill", k=10, entity_type="monetaryItemType")
    assert "us-gaap:Goodwill" in hits


def test_taxonomy_type_filter():
    hits = tools.taxonomy_search("earnings per share basic", k=10, entity_type="perShareItemType")
    assert "us-gaap:EarningsPerShareBasic" in hits


def test_formula_lookup():
    f = tools.formula_lookup("Net Present Value (NPV)")
    assert f and "NPV" in f["formula"]
    assert tools.formula_lookup("no such formula") is None


def test_fincl_query_text():
    q = "table: <entity> 19 </entity> <entity type> monetaryItemType </entity type> <context> Electric — Other revenues | $ | 19 </context>"
    assert "Other revenues" in tools.fincl_query_text({"query": q})
