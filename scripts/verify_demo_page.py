"""Check every number on the rendered page against the raw files, independently of demo/data.js.

Usage: PYTHONUTF8=1 python scripts/verify_demo_page.py <page_text.txt>
The page text is the browser's innerText of demo/index.html?all (both tabs shown). The script recomputes
each fact from data/v1, results/generations (Windows), results/mac/m4/generations (Mac), the profile files
and the taxonomy file, then checks that each recomputed value is on the page and that every number on the
page is one of them. It also checks the claims the page makes in words. It exits non-zero on any problem.
"""
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fineval import prompts, scorers, stats  # noqa: E402

MODELS = ["qwen2.5-1.5b", "gemma2-2b", "qwen2.5-3b", "llama3.2-3b", "qwen2.5-7b", "mistral-7b", "llama3.1-8b"]
NAMES = r"Qwen2\.5-1\.5B|Gemma-2-2B|Qwen2\.5-3B|Llama-3\.2-3B|Qwen2\.5-7B|Mistral-7B|Llama-3\.1-8B|GPT-4o"
CONDS = ["closed", "tools_noorac", "tools_numeric", "tools"]
PROFILED = ["closed", "tools_noorac", "tools"]


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def main(page_path):
    page = Path(page_path).read_text(encoding="utf-8")
    test = {i["uid"]: i for i in jl(ROOT / "data/v1/test/concept_tagging.jsonl")}
    fincl = [i for i in test.values() if i["subset"] == "fincl_subset" and i["primary"]]
    tax = jl(ROOT / "data/raw/fintagging/taxonomy/us_gaap_2024_BM25.jsonl")
    expected, problems = {}, []

    def ok(label, value):
        expected[label] = value

    def need(cond, msg):
        if not cond:
            problems.append(msg)

    ok("taxonomy concepts", f"{len(tax):,}")
    ok("scored items", str(len(fincl)))
    ok("candidates per item (prompts.TAG_CANDIDATES)", str(prompts.TAG_CANDIDATES))

    def tag_run(folder, m, t):
        g = {x["uid"]: x for x in jl(folder / f"{m}__concept_tagging__{t}__s0.jsonl")}
        ex, cov = [], []
        for it in fincl:
            x = g[it["uid"]]
            ex.append(scorers.concept_exact(x["output"] if x["status"] == "ok" else "", it["gold"])["exact"])
            if t != "closed":
                cov.append(any(c in x["tool_log"]["candidates"] for c in it["gold"]["concepts"]))
        return ex, cov

    win = {}
    for m in MODELS:
        for t in CONDS:
            ex, cov = tag_run(ROOT / "results/generations", m, t)
            win[(m, t)] = ex
            hits = int(sum(ex))
            ok(f"{m} {t} accuracy", f"{100 * hits / len(fincl):.1f}%")
            ok(f"{m} {t} correct", f"{hits} / {len(fincl)}")
            if cov:
                covered, both = sum(cov), int(sum(e for e, c in zip(ex, cov) if c))
                ok(f"{t} coverage", f"{100 * covered / len(fincl):.1f}%")
                ok(f"{t} covered items", f"{covered} of {len(fincl)}")
                ok(f"{m} {t} selected-if-covered", f"{100 * both / covered:.1f}%")
                ok(f"{m} {t} picked when covered", f"{both} of {covered}")

    # Mac accuracy beside the Windows score, and the claim that each Mac score is inside the Windows 95% CI
    for gen in sorted((ROOT / "results/mac/m4/generations").glob("*__concept_tagging__*__s0.jsonl")):
        m, _, t, _ = gen.stem.split("__")
        ex, _ = tag_run(gen.parent, m, t)
        acc = sum(ex) / len(ex)
        lo, hi = stats.bootstrap_ci(win[(m, t)])
        need(lo <= acc <= hi, f"Mac {m} {t} {acc:.3f} is outside the Windows CI [{lo:.3f}, {hi:.3f}]")
        ok(f"mac {m} {t} accuracy", f"{100 * acc:.1f}%")
        ok(f"mac {m} {t} beside windows", f"Windows {100 * sum(win[(m, t)]) / len(fincl):.1f}%")

    # cost blocks, straight from the profile files; the page says the model is fully on the GPU
    for machine, folder in (("windows", ROOT / "results/profile/rtx-4050-laptop-gpu"),
                            ("mac", ROOT / "results/mac/m4/profile/m4")):
        for m in MODELS:
            files = [folder / f"{m}__{t}__n100.json" for t in PROFILED]
            ds = [json.loads(f.read_text(encoding="utf-8")) for f in files if f.exists()]
            if not ds:
                continue
            for d in ds:
                pk = d["summary"]["memory_peak_mib"]
                need(d["on_ac_power"] is not False, f"{machine} {m} {d['track']} profiled on battery")
                need(pk["ollama_size_vram_mib"] == pk["ollama_size_mib"], f"{machine} {m} {d['track']} not fully on GPU")
                lat = statistics.median(r["wall_s"] for r in d["per_item"])
                ok(f"{machine} {m} {d['track']} median latency", f"{round(lat, 2):.2f} s")
                ok("profiled items", str(d["n"]))
                ok(f"{machine} ollama", d["ollama_version"])
                ok(f"{machine} ram", str(round(d["machine"]["ram_gb"])))
            ok(f"{machine} {m} model in memory", f"{max(d['summary']['memory_peak_mib']['ollama_size_mib'] for d in ds):,}")
            if machine == "windows":
                ok(f"{m} gpu peak", f"{max(d['summary']['gpu_peak_minus_baseline_mib'] for d in ds):,}")

    # calculation tab
    calc = [i for i in jl(ROOT / "data/v1/test/financial_calc.jsonl") if i["primary"]]
    ok("calc items", f"{len(calc):,}")
    ok("calc formulas", str(len({i["input"]["formula_name"].strip().lower() for i in calc})))
    for m in [m for m in MODELS if all((ROOT / f"results/scores/{m}__financial_calc__{t}__s0.json").exists()
                                       for t in ("closed", "tools"))]:
        for t in ("closed", "tools"):
            g = {x["uid"]: x for x in jl(ROOT / f"results/generations/{m}__financial_calc__{t}__s0.jsonl")}
            hits = int(sum(scorers.numeric_match(g[i["uid"]]["output"] if g[i["uid"]]["status"] == "ok" else "",
                                                 i["gold"])["final"] for i in calc))
            ok(f"calc {m} {t} accuracy", f"{100 * hits / len(calc):.1f}%")
            ok(f"calc {m} {t} correct", f"{hits:,} / {len(calc):,}")
            if t == "tools":
                found = sum(1 for i in calc if (g[i["uid"]]["tool_log"] or {}).get("formula") and
                            g[i["uid"]]["tool_log"]["formula"]["name"] == i["input"]["formula_name"].strip().lower())
                ok("calc formula found", f"{found:,} of {len(calc):,}")
    ok("calc tolerance", "1%")

    # oracle labelling: the `tools` runs filter the search to the item's given type (prompts.py). Check that this
    # type equals the gold concept's type on every scored item, and that the page says so.
    ttype = {"us-gaap:" + r["us_gaap_tag"]: r["entity_type"] for r in tax}
    same = sum(all(ttype.get(c) == it["input"]["entity_type"] for c in it["gold"]["concepts"]) for it in fincl)
    print(f"  given item type == gold concept type on {same} of {len(fincl)} scored items")
    need(same == len(fincl), f"oracle claim is false: given type equals gold type on only {same} of {len(fincl)} items")
    need("diagnostic only" in page, "the oracle column is not marked 'diagnostic only'")
    need("Oracle diagnostic:" in page, "the note explaining the oracle diagnostic is missing")
    need("Calculation" in page and "Accuracy: compute a financial formula" in page, "calculation tab text missing (use ?all)")

    # published, FinTagging arXiv:2505.20650v5 Table 8 FinCL column: GPT-4o 0.1829, Llama-3.1-8B-Instruct 0.0913
    ok("published GPT-4o", f"{100 * 0.1829:.1f}%")
    ok("published Llama-3.1-8B", f"{100 * 0.0913:.1f}%")
    ok("confidence level", "95%")
    # examples: row text, number, gold and Qwen2.5-7B oracle-search prediction must match the raw files
    qg = {x["uid"]: x for x in jl(ROOT / "results/generations/qwen2.5-7b__concept_tagging__tools__s0.jsonl")}
    for uid in ("fintagging:fincl_subset:test:10", "fintagging:fincl_subset:test:1"):
        it, x = test[uid], qg[uid]
        row = re.search(r"<context>(.*?)</context>", it["input"]["query"], re.S).group(1).strip()
        for label, val in (("row", row), ("gold", it["gold"]["concepts"][0]),
                           ("prediction", scorers.parse_concept(x["output"])), ("number", it["input"]["entity"])):
            need(val in page, f"example {uid} {label} not on page: {val}")
        ok(f"example {uid} number", it["input"]["entity"])
        ok(f"example {uid} row numbers", " ".join(re.findall(r"\d[\d.,]*", row)))

    for label, val in expected.items():
        if "row numbers" not in label:
            need(val in page, f"MISSING on page: {label} = {val}")
    # every number on the page must be explained by a recomputed value (or a model / hardware name)
    text = re.sub(r"us-gaap:\S+", " ", page)
    text = re.sub(NAMES + r"|US-GAAP|XBRL|SEC|RTX 4050|i5-13420H|13th Gen|Apple M4|CC-BY-4.0", " ", text)
    allowed = set()
    for v in expected.values():
        allowed.update(re.findall(r"\d[\d.,]*\d|\d", v))
    for n in re.findall(r"\d[\d.,]*\d|\d", text):
        need(n in allowed, f"UNEXPLAINED number on page: {n}")
    for label, val in expected.items():
        print(f"  {label:45s} {val}")
    if problems:
        print("\nPROBLEMS:\n" + "\n".join(dict.fromkeys(problems)))
        sys.exit(1)
    print("\nALL NUMBERS ON THE PAGE MATCH THE RAW FILES.")


if __name__ == "__main__":
    main(sys.argv[1])
