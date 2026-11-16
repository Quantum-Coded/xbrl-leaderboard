"""Check every number on the rendered demo page against the raw files, independently of demo/data.js.

Usage: PYTHONUTF8=1 python scripts/verify_demo_page.py <page_text.txt>
The page text is the browser's innerText of demo/index.html. The script recomputes each fact from
data/v1, results/generations and the taxonomy file, then checks that every number on the page
is one of these recomputed values. It exits non-zero on any mismatch or unexplained number.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fineval import scorers, prompts  # noqa: E402


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def main(page_path):
    page = Path(page_path).read_text(encoding="utf-8")
    test = {i["uid"]: i for i in jl(ROOT / "data/v1/test/concept_tagging.jsonl")}
    fincl = [i for i in test.values() if i["subset"] == "fincl_subset" and i["primary"]]
    taxonomy = sum(1 for _ in jl(ROOT / "data/raw/fintagging/taxonomy/us_gaap_2024_BM25.jsonl"))
    expected, problems = {}, []

    def ok(label, value):
        expected[label] = value

    ok("taxonomy concepts", f"{taxonomy:,}")
    ok("scored items", str(len(fincl)))
    ok("candidates per item (prompts.TAG_CANDIDATES)", str(prompts.TAG_CANDIDATES))
    runs = {}
    for m in ("llama3.1-8b", "qwen2.5-7b", "qwen2.5-3b"):
        for t in ("closed", "tools"):
            g = {x["uid"]: x for x in jl(ROOT / f"results/generations/{m}__concept_tagging__{t}__s0.jsonl")}
            hits = covered = both = 0
            for it in fincl:
                x = g[it["uid"]]
                e = scorers.concept_exact(x["output"] if x["status"] == "ok" else "", it["gold"])["exact"]
                hits += e
                if t == "tools":
                    c = any(c in x["tool_log"]["candidates"] for c in it["gold"]["concepts"])
                    covered += c
                    both += c and e
            runs[(m, t)] = dict(hits=int(hits), covered=covered, both=int(both))
            ok(f"{m} {t} accuracy", f"{100 * hits / len(fincl):.1f}%")
            ok(f"{m} {t} correct", f"{int(hits)} / {len(fincl)}")
            if t == "tools":
                ok(f"{m} coverage", f"{100 * covered / len(fincl):.1f}%")
                ok(f"{m} covered items", str(covered))
                ok(f"{m} selected-if-covered", f"{100 * both / covered:.1f}%")
                ok(f"{m} picked when covered", f"{int(both)} of {covered}")
    # oracle labelling: the `tools` runs filter the search to the item's given type (prompts.py). Check that this
    # type equals the gold concept's type on every scored item, and that every such row is labelled on the page.
    ttype = {"us-gaap:" + r["us_gaap_tag"]: r["entity_type"]
             for r in jl(ROOT / "data/raw/fintagging/taxonomy/us_gaap_2024_BM25.jsonl")}
    same = sum(all(ttype.get(c) == it["input"]["entity_type"] for c in it["gold"]["concepts"]) for it in fincl)
    print(f"  given item type == gold concept type on {same} of {len(fincl)} scored items")
    if same != len(fincl):
        problems.append(f"oracle claim is false: given type equals gold type on only {same} of {len(fincl)} items")
    label = "given item type: oracle diagnostic"
    oracle_rows = sum(1 for (_, t) in runs if t == "tools")
    if page.count(label) != oracle_rows:
        problems.append(f"expected '{label}' on {oracle_rows} result rows, found {page.count(label)}")
    if "Oracle diagnostic:" not in page:
        problems.append("the note explaining the oracle diagnostic is missing")
    # no-oracle runs are not on the page yet; fail loudly when they arrive so the page gets updated
    noorac = sorted((ROOT / "results/generations").glob("*__concept_tagging__tools_noorac__s0.jsonl"))
    if noorac:
        problems.append("no-oracle runs exist: add them to build_demo.py TRACKS and to this check")
    # latency and memory: no profile files are read here, so the page must not show any
    for word in ("Latency", "Peak memory"):
        if word in page:
            problems.append(f"page shows '{word}', but this script checks no latency or memory numbers")
    # published, FinTagging arXiv:2505.20650v5 Table 8 FinCL column: GPT-4o 0.1829, Llama-3.1-8B-Instruct 0.0913
    ok("published GPT-4o", f"{100 * 0.1829:.1f}%")
    ok("published Llama-3.1-8B", f"{100 * 0.0913:.1f}%")
    # examples: row text, number, gold and Qwen2.5-7B tools prediction must match the raw files
    qg = {x["uid"]: x for x in jl(ROOT / "results/generations/qwen2.5-7b__concept_tagging__tools__s0.jsonl")}
    for uid in ("fintagging:fincl_subset:test:10", "fintagging:fincl_subset:test:1"):
        it, x = test[uid], qg[uid]
        row = re.search(r"<context>(.*?)</context>", it["input"]["query"], re.S).group(1).strip()
        for label, val in (("row", row), ("gold", it["gold"]["concepts"][0]),
                           ("prediction", scorers.parse_concept(x["output"])), ("number", it["input"]["entity"])):
            if val not in page:
                problems.append(f"example {uid} {label} not on page: {val}")
        ok(f"example {uid} number", it["input"]["entity"])
        ok(f"example {uid} row numbers", " ".join(re.findall(r"\d[\d.,]*", row)))

    for label, val in expected.items():
        if "row numbers" in label:
            continue
        if val not in page:
            problems.append(f"MISSING on page: {label} = {val}")
    # every number on the page must be explained by a recomputed value (or a model name / rank / concept name)
    text = re.sub(r"us-gaap:\S+", " ", page)
    text = re.sub(r"Llama-3\.1-8B|Qwen2\.5-7B|Qwen2\.5-3B|GPT-4o|US-GAAP|XBRL|SEC", " ", text)
    allowed = set()
    for v in expected.values():
        allowed.update(re.findall(r"\d[\d.,]*\d|\d", v))
    # rank column: 1 + number of runs with a strictly higher accuracy (ties share a rank)
    accs = [round(100 * r["hits"] / len(fincl), 1) for r in runs.values()]
    ranks = sorted(1 + sum(o > a for o in accs) for a in accs)
    allowed.update(str(r) for r in ranks)
    rows_on_page = re.findall(r"^(\d+)\t(?:Llama|Qwen)", page, re.M)
    if sorted(int(r) for r in rows_on_page) != ranks:
        problems.append(f"rank column {rows_on_page} does not match recomputed ranks {ranks}")
    for n in re.findall(r"\d[\d.,]*\d|\d", text):
        if n not in allowed:
            problems.append(f"UNEXPLAINED number on page: {n}")
    for label, val in expected.items():
        print(f"  {label:45s} {val}")
    print(f"\nRanks {ranks} follow from the accuracies above (ties share a rank).")
    if problems:
        print("\nPROBLEMS:\n" + "\n".join(problems))
        sys.exit(1)
    print("\nALL NUMBERS ON THE PAGE MATCH THE RAW FILES.")


if __name__ == "__main__":
    main(sys.argv[1])
