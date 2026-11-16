"""Compare our FinCL scorer (scorers.concept_exact) with FinTagging's official FinCL evaluation, item by item.

    python -I scripts/scorer_check_fincl.py

Official code: The-FinAI/FinTagging @ ff426bc4c914c3cc6d967a696fbc041ed157c459, evaluate_NEN.ipynb
(MIT licence). Its three functions are reproduced below unchanged, apart from taking the candidate list
from our tool log instead of re-parsing it from the prompt (the candidates are the same list). The
official evaluation:
  - normalises the response and reads {"result": ...};
  - if that fails or the result is "None", answers with the FIRST CANDIDATE (candidates[0]);
  - scores exact string equality with the gold concept.
It is defined only for prompts with candidates (our tools tracks). For closed-book runs there is no
candidate to fall back to, so a failed parse is scored wrong ("official parse, no fallback").
Writes results/scorer_check/fincl.json.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fineval import data, run, scorers  # noqa: E402


# ---- FinTagging evaluate_NEN.ipynb (verbatim) ----------------------------------------------------
def normalize_response(text_str):
    pattern = r"\{\"result\"\s*:\s*(.*?)\}"

    code_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text_str, flags=re.DOTALL)
    if code_block_match:
        text_str = code_block_match.group(1).strip()
    else:
        json_match = re.search(pattern, text_str)
        if json_match:
            text_str = json_match.group(1)
            if text_str.startswith('{') and text_str.endswith('}'):
                text_str = text_str.replace("\n", "").strip()
            else:
                text_str = f"""{{"result": {text_str}}}"""
        else:
            text_str = """{{"result": "None"}}"""

    text_str = text_str.replace("\n", "").strip()
    return text_str.strip()


def official_prediction(response, candidates):
    """The notebook's per-line logic. Returns (prediction, used_fallback)."""
    response = normalize_response(response)
    try:
        response = json.loads(response)
        response = response.get("result")
        if response == "None":
            return (candidates[0] if candidates else None), True
    except Exception:  # noqa: BLE001  (the notebook uses a bare except)
        return (candidates[0] if candidates else None), True
    return response, False
# ---------------------------------------------------------------------------------------------------


def main():
    fincl = [i for i in data.items("concept_tagging") if i["subset"] == "fincl_subset" and i["primary"]]
    out = {"official_code": "The-FinAI/FinTagging@ff426bc4c914c3cc6d967a696fbc041ed157c459:evaluate_NEN.ipynb",
           "n_items": len(fincl), "runs": {}}
    for f in sorted(run.GEN.glob("*__concept_tagging__*__s0.jsonl")):
        name = f.stem
        track = name.split("__")[2]
        gens = {json.loads(l)["uid"]: json.loads(l) for l in f.open(encoding="utf-8")}
        if not all(i["uid"] in gens for i in fincl):
            continue
        ours = official = fallbacks = fallback_correct = 0
        diffs = []
        for it in fincl:
            g = gens[it["uid"]]
            text = g["output"] if g["status"] == "ok" else ""
            cands = (g.get("tool_log") or {}).get("candidates") or []
            a = scorers.concept_exact(text, it["gold"])["exact"] == 1.0
            gold = it["gold"]["concepts"][0]          # primary items have exactly one gold concept
            pred, fb = official_prediction(text, cands)
            b = isinstance(pred, str) and pred == gold
            ours += a
            official += b
            fallbacks += fb
            fallback_correct += fb and b
            if a != b:
                diffs.append({"uid": it["uid"], "ours": a, "official": b, "official_fallback": fb,
                              "our_parse": scorers.parse_concept(text), "official_pred": pred,
                              "gold": gold, "output": text[:300]})
        n = len(fincl)
        out["runs"][name] = {
            "track": track, "candidates_in_prompt": track != "closed",
            "ours": {"correct": ours, "accuracy": round(ours / n, 4)},
            "official": {"correct": official, "accuracy": round(official / n, 4),
                         "note": "first-candidate fallback" if track != "closed" else "official parse, no fallback"},
            "official_fallbacks": fallbacks, "fallback_correct": fallback_correct,
            "items_disagreeing": len(diffs), "disagreements": diffs}
        print(f"{name:45s} ours {ours:3d}  official {official:3d}  fallbacks {fallbacks:3d} "
              f"(correct {fallback_correct})  disagree {len(diffs)}")
    assert any(1 for _ in fincl) and len({i['uid'] for i in fincl}) == 484, "expected 484 scored FinCL items"
    dest = ROOT / "results" / "scorer_check" / "fincl.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote", dest.relative_to(ROOT))


if __name__ == "__main__":
    main()
