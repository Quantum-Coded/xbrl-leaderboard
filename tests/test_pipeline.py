"""Run -> score end to end with the mock backend (no GPU)."""
import json

import pytest

from fineval import data, prompts, run, score


@pytest.fixture
def tmp_results(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "GEN", tmp_path / "gen")
    monkeypatch.setattr(score, "GEN", tmp_path / "gen")
    monkeypatch.setattr(score, "SCORES", tmp_path / "scores")
    return tmp_path


def test_fixed_answer_scores_exactly_its_gold_share(tmp_results):
    ans = "us-gaap:AccountsReceivableNetCurrent"
    run.main(["--model", f"mock:fixed:Answer: {ans}", "--task", "concept_tagging", "--n", "120"])
    name = run.run_name(f"mock:fixed:Answer: {ans}", "concept_tagging", "closed", 0, 120)
    res = score.score_run(name)
    items = [i for i in data.sample("concept_tagging", 120) if i["primary"]]
    expected = sum(ans in i["gold"]["concepts"] for i in items) / len(items)
    assert res["primary"]["value"] == pytest.approx(expected)
    assert res["status"] == {"ok": 120}


def test_resume_does_not_duplicate(tmp_results):
    args = ["--model", "mock:echo", "--task", "financial_calc", "--n", "30"]
    run.main(args + ["--limit", "10"])
    out = run.main(args)
    lines = [json.loads(l) for l in out.open(encoding="utf-8")]
    assert len(lines) == 30 and len({l["uid"] for l in lines}) == 30


def test_missing_items_score_zero(tmp_results):
    run.main(["--model", "mock:fixed:Answer: 21462.58", "--task", "financial_calc", "--n", "40", "--limit", "5"])
    res = score.score_run(run.run_name("mock:fixed:Answer: 21462.58", "financial_calc", "closed", 0, 40))
    assert res["primary"]["n"] == 40 and res["status"]["missing"] == 35


def test_tools_calc_evaluates_expression():
    f = prompts.formula_search("Compute the net present value NPV of the discounted cash flows")
    assert f and "net present value" in f["name"]
    item = next(i for i in data.items("financial_calc") if i["uid"] == "xbrl_agent:formula:test:0-1")
    _, user, log = prompts.build(item, "tools")
    assert "formula" in log and "Question:" in user
    out, calc = prompts.finish_tools_calc("Expression: sum(6000/(1.08)**t for t in range(1,5))")
    assert calc["value"] == pytest.approx(19872.76, abs=0.01)
    out, calc = prompts.finish_tools_calc("Expression: __import__('os')")
    assert "error" in calc and "Answer:" not in out


def test_fincl_tools_prompt_lists_typed_candidates():
    item = next(i for i in data.items("concept_tagging") if i["subset"] == "fincl_subset")
    _, user, log = prompts.build(item, "tools")
    assert len(log["candidates"]) == prompts.TAG_CANDIDATES and "Candidate Tags:" in user


def test_context_never_silently_truncated():
    assert run.ctx_for(None, "x" * 30000, 1024) > run.CTX_CAP
    assert run.ctx_for(None, "x" * 3000, 64) <= 2048


def test_tag_tracks_differ_only_in_type_filter():
    from fineval import tools
    item = next(i for i in data.items("concept_tagging") if i["subset"] == "fincl_subset")
    rows, _ = tools._taxonomy()
    ttype = {"us-gaap:" + r["us_gaap_tag"]: r["entity_type"] for r in rows}
    q = tools.fincl_query_text(item["input"])
    _, _, oracle = prompts.build(item, "tools")
    _, user, noorac = prompts.build(item, "tools_noorac")
    _, _, numeric = prompts.build(item, "tools_numeric")
    assert {ttype[c] for c in oracle["candidates"]} == {item["input"]["entity_type"]}      # oracle: given type only
    assert noorac["candidates"] == tools.taxonomy_search(q, k=prompts.TAG_CANDIDATES)      # no type information
    assert all(ttype[c] in tools.NUMERIC_TYPES for c in numeric["candidates"])
    assert all(len(log["candidates"]) == prompts.TAG_CANDIDATES for log in (oracle, noorac, numeric))


def test_new_tag_tracks_rejected_outside_concept_tagging():
    item = next(iter(data.items("financial_calc")))
    with pytest.raises(ValueError):
        prompts.build(item, "tools_noorac")
    with pytest.raises(SystemExit):
        run.main(["--model", "mock:echo", "--task", "financial_calc", "--track", "tools_numeric", "--limit", "1"])


def test_results_root_defaults_to_repo_results():
    assert run.GEN == run.ROOT / "results" / "generations" and score.SCORES == run.ROOT / "results" / "scores"
