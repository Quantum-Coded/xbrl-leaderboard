"""Phase 1-2: pinned sources, loader counts, round-trip fixtures, schema."""
import json
import random
from collections import Counter

import pandas as pd
import pytest

from fineval.fetch import RAW, load_manifest, verify
from fineval.schema import validate
from fineval.sources.loaders import load_all
from fineval.sources.registry import SOURCES


@pytest.fixture(scope="module")
def loaded():
    return load_all()


def test_manifest_matches_files():
    assert verify() == []


def test_every_registered_file_is_pinned():
    m = load_manifest()
    for source, s in SOURCES.items():
        for path in s["files"]:
            rec = m[f"{source}/{path}"]
            assert rec["commit"] == s["commit"] and len(rec["sha256"]) == 64


def test_schema_and_unique_uids(loaded):
    for r in loaded.records:
        validate(r.to_dict())
    assert len({r.uid for r in loaded.records}) == len(loaded.records)


def _rows(key, **kw):
    p = RAW / key
    if key.endswith(".jsonl"):
        return len(p.read_text(encoding="utf-8").splitlines())
    if key.endswith(".xlsx"):
        return len(pd.read_excel(p))
    return len(pd.read_csv(p, sep="\t" if key.endswith(".tsv") else ",", **kw))


def test_counts_equal_raw_rows_minus_skipped(loaded):
    """Every raw row becomes a record or a logged skip; nothing disappears."""
    made = Counter(r.provenance["file"] for r in loaded.records)
    skipped = Counter(s["file"] for s in loaded.skipped)
    wide = {"xbrl_agent/Datasets/formulas_with_explanations_with_questions_with_gt.xlsx": 20,
            "coling/validation/Task7-XBRL/Task7-XBRL-financial_math-validation.csv": 20}
    for key in made:
        if key.endswith("TrainingSet_Annotation.json"):
            d = json.loads((RAW / key).read_text(encoding="utf-8"))
            assert made[key] == len(d["text_data"]) + len(d["table_data"])
            continue
        assert made[key] + skipped[key] == _rows(key) * wide.get(key, 1), key


def test_known_sizes(loaded):
    c = Counter((r.source, r.subset, r.source_split) for r in loaded.records)
    assert c[("financebench", "open", "test")] == 150
    assert c[("xbrl_agent", "formula", "test")] == 1000
    assert c[("xbrl_agent", "financebench", "test")] == 149
    assert c[("fintagging", "fincl_subset", "test")] == 500
    assert c[("fintagging", "finni_subset", "test")] == 200
    assert c[("coling", "tag_query", "test")] == 90
    assert c[("coling", "math", "test")] == 90
    assert c[("coling", "domain_numeric", "test")] + c[("coling", "domain_numeric", "validation")] == 99


def _get(loaded, uid):
    return next(r for r in loaded.records if r.uid == uid)


def test_roundtrip_fixtures(loaded):
    r = _get(loaded, "xbrl_agent:formula:test:0-1")
    assert r.input["question"] == ("A project expects annual cash inflows of $6,000 for 4 years. "
                                   "If the discount rate is 8%, what is the NPV of the project?")
    assert r.gold == {"value": 21462.58} and r.input["formula_name"] == "Net Present Value (NPV)"

    r = _get(loaded, "financebench:open:test:financebench_id_03029")
    assert r.gold["answer"] == "$1577.00" and r.filing_key == "3M_2018_10K"

    r = _get(loaded, "coling:tag_query:test:0")
    assert r.gold == {"concepts": ["us-gaap:AccountsReceivableNetCurrent"]} and r.filing_key == "BA|ba-20231231"

    r = _get(loaded, "fintagging:fincl_subset:test:0")
    assert r.gold == {"concepts": ["us-gaap:RevenueNotFromContractWithCustomerOther"]}
    assert r.input["entity"] == "19" and r.input["entity_type"] == "monetaryItemType"

    r = _get(loaded, "fintagging:finni_subset:test:5513")
    assert r.gold == {"facts": [{"fact": "46", "type": "monetaryItemType"}]}


def test_random_records_trace_back_to_raw_rows(loaded):
    """20 random records per source: the gold value is found in the raw row named by provenance."""
    rng = random.Random(0)
    by_source = {}
    for r in loaded.records:
        by_source.setdefault(r.source, []).append(r)
    cache = {}
    for source, recs in by_source.items():
        for r in rng.sample(recs, min(20, len(recs))):
            key, row = r.provenance["file"], r.provenance["row"]
            if key not in cache:
                p = RAW / key
                if key.endswith(".jsonl"):
                    cache[key] = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()]
                elif key.endswith(".json"):
                    d = json.loads(p.read_text(encoding="utf-8"))
                    cache[key] = {"text_data": d["text_data"], "table_data": d["table_data"]}
                elif key.endswith(".xlsx"):
                    cache[key] = pd.read_excel(p).to_dict("records")
                else:
                    cache[key] = pd.read_csv(p, sep="\t" if key.endswith(".tsv") else ",").to_dict("records")
            raw = cache[key]
            if isinstance(raw, dict):
                raw_row = raw["text_data" if r.subset == "train_text" else "table_data"][row]
            else:
                raw_row = raw[row]
            blob = json.dumps(raw_row, ensure_ascii=False, default=str)
            g = r.gold
            probe = (g.get("answer") or g.get("definition") or (g.get("concepts") or [None])[0]
                     or (g["facts"][0]["fact"] if g.get("facts") else None))
            if "value" in g:
                probe = None
                assert any(isinstance(v, float) and abs(v - g["value"]) < 1e-9 for v in raw_row.values()), r.uid
            if probe is not None:
                assert json.dumps(probe, ensure_ascii=False)[1:-1] in blob, r.uid
