"""Compare a second machine's FinCL runs with the committed (Windows) runs, item by item.

    python -I scripts/compare_machines.py results/mac/m4

For every run in <folder>/generations it rescores the 484 scored FinCL items with scorers.concept_exact
and reports accuracy with a 95% bootstrap CI. When a run of the same name exists in results/generations
(the committed Windows run) it also reports, on the same items:
  - how many prompts are identical (prompt_sha1), so the two machines saw the same inputs;
  - how many raw outputs are identical, and how many parsed answers are identical;
  - how many items are scored differently, with their ids.
For tag-search runs it reports how often the gold concept is among the candidates.
It also lists latency and peak memory from <folder>/profile/, if present. These are this machine's
numbers only and must not be mixed with another machine's.
Writes <folder>/compare_windows.json. Nothing is estimated: every value is recomputed from the files.
"""
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fineval import scorers, stats  # noqa: E402


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def pct(x):
    return round(100 * x, 1)


def main(folder):
    folder = (ROOT / folder).resolve()
    test = [i for i in jl(ROOT / "data/v1/test/concept_tagging.jsonl") if i["subset"] == "fincl_subset" and i["primary"]]
    out = {"folder": str(folder.relative_to(ROOT)).replace("\\", "/"), "reference": "results/generations",
           "items": len(test), "runs": []}
    for gen in sorted((folder / "generations").glob("*__concept_tagging__*__s0.jsonl")):
        name = gen.stem
        meta = json.loads(gen.with_name(name + ".meta.json").read_text(encoding="utf-8"))
        mine = {g["uid"]: g for g in jl(gen)}
        ref_path = ROOT / "results/generations" / gen.name
        ref = {g["uid"]: g for g in jl(ref_path)} if ref_path.exists() else None
        ref_meta = (json.loads(ref_path.with_name(name + ".meta.json").read_text(encoding="utf-8")) if ref else None)

        def answer(g):
            return g["output"] if g and g["status"] == "ok" else ""

        exact = [scorers.concept_exact(answer(mine.get(i["uid"])), i["gold"])["exact"] for i in test]
        lo, hi = stats.bootstrap_ci(exact)
        r = {"run": name, "model": meta["model"], "model_digest": meta["model_digest"][:12], "runtime": meta.get("runtime"),
             "track": meta["track"], "machine": meta.get("machine"), "generated": sum(i["uid"] in mine for i in test),
             "correct": int(sum(exact)), "accuracy": pct(sum(exact) / len(exact)), "ci95": [pct(lo), pct(hi)]}
        stored = folder / "scores" / f"{name}.json"
        if stored.exists():
            s = json.loads(stored.read_text(encoding="utf-8"))["by_subset"]["fincl_subset"]
            assert s["n"] == len(exact) and abs(s["value"] - sum(exact) / len(exact)) < 1e-12, (name, s["value"])
            r["equals_stored_score_file"] = True
        if meta["track"] != "closed":
            cov = [any(c in mine[i["uid"]]["tool_log"]["candidates"] for c in i["gold"]["concepts"]) for i in test]
            both = sum(1 for c, e in zip(cov, exact) if c and e)
            r["covered_items"] = sum(cov)
            r["coverage"] = pct(sum(cov) / len(cov))
            r["selected_covered_items"] = both
            r["selected_if_covered"] = pct(both / sum(cov))
            r["correct_outside_candidates"] = int(sum(exact)) - both
        if ref is None:
            r["reference_run"] = None
        else:
            ref_exact = [scorers.concept_exact(answer(ref.get(i["uid"])), i["gold"])["exact"] for i in test]
            differ = [i["uid"] for i, a, b in zip(test, exact, ref_exact) if a != b]
            r["reference_run"] = {
                "runtime": ref_meta.get("runtime"), "model_digest": ref_meta["model_digest"][:12],
                "same_model_digest": ref_meta["model_digest"] == meta["model_digest"],
                "correct": int(sum(ref_exact)), "accuracy": pct(sum(ref_exact) / len(ref_exact)),
                "same_prompt": sum(mine[i["uid"]]["prompt_sha1"] == ref[i["uid"]]["prompt_sha1"] for i in test),
                "same_raw_output": sum(mine[i["uid"]].get("raw_output") == ref[i["uid"]].get("raw_output") for i in test),
                "same_parsed_answer": sum(scorers.parse_concept(answer(mine[i["uid"]])) == scorers.parse_concept(answer(ref[i["uid"]]))
                                          for i in test),
                "scored_differently": len(differ),
                "this_machine_only_correct": [i["uid"] for i, a, b in zip(test, exact, ref_exact) if a > b],
                "reference_only_correct": [i["uid"] for i, a, b in zip(test, exact, ref_exact) if a < b],
            }
        out["runs"].append(r)
        print(json.dumps({k: v for k, v in r.items() if k != "machine"}, indent=1))

    profiles = []
    for p in sorted((folder / "profile").glob("*/*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        profiles.append({"file": str(p.relative_to(ROOT)).replace("\\", "/"), **{k: v for k, v in d.items() if k not in ("items", "per_item")}})
    out["profiles"] = profiles
    (folder / "compare_windows.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("wrote", folder / "compare_windows.json", "| profiles:", len(profiles))


if __name__ == "__main__":
    main(sys.argv[1])
