"""Golden tests: hand-written outputs pinned to expected scores, edge cases included."""
import pytest

from fineval.scorers import aggregate, concept_exact, finni_pairs, numeric_match, parse_concept
from fineval.stats import bootstrap_ci, noise_groups, paired_bootstrap

G = {"concepts": ["us-gaap:AccountsReceivableNetCurrent"]}


@pytest.mark.parametrize("out,exact,ci", [
    ('{"result": "us-gaap:AccountsReceivableNetCurrent"}', 1, 1),
    ("Answer: us-gaap:AccountsReceivableNetCurrent", 1, 1),
    ("Answer:us-gaap:AccountsReceivableNetCurrent", 1, 1),
    ("The tag is us-gaap:AccountsReceivableNetCurrent because ...", 1, 1),
    ("Answer: AccountsReceivableNetCurrent", 0, 1),                 # no prefix: strict miss
    ("Answer: us-gaap:accountsreceivablenetcurrent", 0, 1),         # case: strict miss
    ("Answer: us-gaap:AccountsReceivableNet", 0, 0),
    ("I cannot determine the tag.", 0, 0),
    ("", 0, 0),
])
def test_concept_exact(out, exact, ci):
    assert concept_exact(out, G) == {"exact": exact, "ci_element": ci}


def test_concept_any_of_several_golds():
    g = {"concepts": ["us-gaap:A1b", "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"]}
    assert concept_exact("Answer: us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", g)["exact"] == 1


def test_parse_concept_first_prefixed_wins():
    assert parse_concept("Candidates: X. Final: us-gaap:Revenues, not us-gaap:SalesRevenueNet") == "us-gaap:Revenues"


FG = {"facts": [{"fact": "1,200", "type": "monetaryItemType"}, {"fact": "5", "type": "percentItemType"},
                {"fact": "5", "type": "percentItemType"}]}


def test_finni_exact_and_numeric():
    out = '{"result": [{"Fact": "1200", "Type": "monetaryItemType"}, {"Fact": "5", "Type": "percentItemType"}]}'
    s = finni_pairs(out, FG)
    assert (s["strict_tp"], s["strict_fp"], s["strict_fn"]) == (1, 1, 2)     # "1200" != "1,200" verbatim
    assert (s["numeric_tp"], s["numeric_fp"], s["numeric_fn"]) == (2, 0, 1)  # multiset: one "5" left


def test_finni_wrong_type_is_a_miss_and_code_fence_parsed():
    out = '```json\n{"result": [{"Fact": "1,200", "Type": "sharesItemType"}]}\n```'
    s = finni_pairs(out, FG)
    assert s["strict_tp"] == 0 and s["strict_fp"] == 1 and s["parsed"] == 1


def test_finni_unparseable_and_empty():
    assert finni_pairs("no json here", FG)["parsed"] == 0
    assert finni_pairs("no json here", FG)["strict_fn"] == 3
    empty = finni_pairs('{"result": []}', {"facts": []})
    assert (empty["strict_tp"], empty["strict_fp"], empty["strict_fn"], empty["parsed"]) == (0, 0, 0, 1)


def test_finni_aggregate_is_pooled():
    a = finni_pairs('{"result": [{"Fact": "1,200", "Type": "monetaryItemType"}]}', FG)
    b = finni_pairs('{"result": []}', {"facts": [{"fact": "7", "type": "integerItemType"}]})
    agg = aggregate("finni_pair_f1@v1", [a, b])
    assert agg["strict_precision"] == 1.0 and agg["strict_recall"] == pytest.approx(1 / 4)


@pytest.mark.parametrize("out,gold,final,agnostic", [
    ("NPV = 21,462.58", 21462.58, 1, 1),
    ("The NPV is $21,463.", 21462.58, 1, 1),                 # within 1%
    ("Therefore the APR is 41%.", 0.41, 1, 1),              # % read as fraction
    ("Therefore the APR is 0.41.", 0.41, 1, 1),
    ("Therefore the APR is 41.", 0.41, 0, 1),               # bare 41 only under unit-agnostic
    ("Answer: (1,577)", -1577, 1, 1),                       # accounting negative
    ("Answer: 1.5 million", 1500000, 1, 1),
    ("I don't know.", 12.0, 0, 0),
    ("First 12, then = 15", 12.0, 0, 0),                    # only the final segment counts
])
def test_numeric_match(out, gold, final, agnostic):
    s = numeric_match(out, {"value": gold})
    assert (s["final"], s["unit_agnostic"]) == (final, agnostic)


def test_bootstrap_and_paired():
    xs = [1, 0] * 50
    lo, hi = bootstrap_ci(xs)
    assert lo < 0.5 < hi
    assert bootstrap_ci(xs) == bootstrap_ci(xs)                      # seeded
    r = paired_bootstrap([0] * 100, [1] * 100)
    assert r["diff"] == 1 and r["p_not_better"] == 0


def test_noise_groups():
    g = noise_groups({"a": (0.8, (0.75, 0.85)), "b": (0.78, (0.72, 0.84)), "c": (0.5, (0.45, 0.55))})
    assert g == [["a", "b"], ["c"]]


def test_finni_bare_list_is_parsed_but_not_format_ok():
    out = '```json\n[{"Fact": "531", "Type": "monetaryItemType"}]\n```\nNote: extra prose.'
    s = finni_pairs(out, {"facts": [{"fact": "531", "type": "monetaryItemType"}]})
    assert s["parsed"] == 1 and s["format_ok"] == 0 and s["strict_tp"] == 1
    w = finni_pairs('{"result": [{"Fact": "531", "Type": "monetaryItemType"}]}',
                    {"facts": [{"fact": "531", "type": "monetaryItemType"}]})
    assert w["format_ok"] == 1 and w["strict_tp"] == 1
    assert finni_pairs("[1, 2, 3]", FG)["parsed"] == 0          # a list of numbers is not a FinNI answer
