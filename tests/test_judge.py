import pytest

from fineval import judge


@pytest.mark.parametrize("ans", ["I cannot determine this from the information provided.",
                                 "The pages do not contain the answer; it is not provided in the context.",
                                 "I don't have access to the filing.", "N/A", ""])
def test_abstentions_are_failed_without_calling_the_judge(ans):
    item = {"input": {"question": "q"}, "gold": {"answer": "1"}}
    assert judge.judge_one(item, ans, "mock:fixed:CORRECT")["label"] == "FAILED"


def test_judge_label_parsing():
    assert judge.parse_label("CORRECT") == "CORRECT"
    assert judge.parse_label("Grade: incorrect.") == "INCORRECT"
    assert judge.parse_label("hmm") is None
    item = {"input": {"question": "q"}, "gold": {"answer": "1"}}
    r = judge.judge_one(item, "It is $1.", "mock:fixed:no idea")
    assert r["label"] == "INCORRECT" and r["unparsed"]


def test_family():
    assert judge.family("ollama:qwen2.5:7b") == "qwen"
    assert judge.family("ollama:llama3.1:8b") == "llama"
    assert judge.family("ollama:qwen2.5:3b") == judge.family("ollama:qwen2.5:7b")


def test_kappa():
    assert judge.cohen_kappa(list("aabb"), list("aabb")) == 1
    assert judge.cohen_kappa(list("abab"), list("abba")) == pytest.approx(0.0)
