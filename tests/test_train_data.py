"""Phase 7 data: built from train only, same instruction as eval, no test leakage."""
import json

import pytest

from fineval import data
from fineval.normalize import text_key
from fineval.train_data import SFT, finni_instruction


@pytest.fixture(scope="module")
def sft():
    if not (SFT / "stats.json").exists():
        pytest.skip("run python -I -m fineval.train_data first")
    load = lambda n: [json.loads(l) for l in (SFT / f"{n}.jsonl").open(encoding="utf-8")]
    return load("finni"), load("fincl"), json.loads((SFT / "stats.json").read_text(encoding="utf-8"))


def test_counts_match_stats(sft):
    finni, fincl, stats = sft
    assert len(finni) == stats["finni_examples"] == stats["train_items"]
    assert len(fincl) == stats["fincl_examples"]


def test_only_train_uids(sft):
    finni, fincl, _ = sft
    train = {i["uid"] for i in data.items("fact_extraction", "train")}
    assert {e["uid"] for e in finni + fincl} <= train


def test_finni_uses_eval_instruction(sft):
    pre, suf = finni_instruction()
    assert all(e["prompt"].startswith(pre) and e["prompt"].endswith(suf) for e in sft[0])


def test_no_fincl_query_equals_a_test_query(sft):
    test_q = {text_key(i["input"]["query"]) for i in data.items("concept_tagging") if i["subset"] == "fincl_subset"}
    assert not [e for e in sft[1] if text_key(e["query"]) in test_q]


def test_completions_are_valid_json(sft):
    finni, fincl, _ = sft
    for e in finni[:200] + fincl[:200]:
        assert "result" in json.loads(e["completion"])
