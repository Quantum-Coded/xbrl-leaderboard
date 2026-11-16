# FinEval v1

A reproducible benchmark for LLMs on financial reporting: XBRL concept tagging, fact extraction from
filings, financial calculation and filing QA. It combines FinTagging, XBRL-Agent, FinanceBench and the
COLING 2025 Regulations Challenge, removes cross-source duplicates, and keeps published scores apart
from scores reproduced under one common setup.

* Scope and rationale: [`PLAN.md`](PLAN.md)
* Phase-by-phase plan with exit tests: [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md)
* What is in the data, overlaps and conflicts: [`docs/datasheet.md`](docs/datasheet.md) (generated)

## XBRL Leaderboard: reproduce in 3 commands

Saved model outputs are committed in `results/generations/`, so no GPU is needed to check the
numbers. On Windows, replace `.venv/bin/python` with `.venv/Scripts/python`.

```bash
# 1. setup: environment, pinned data (SHA-256 checked), deterministic build
python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.lock.txt && .venv/bin/python -m pip install -e . && .venv/bin/python -I -m fineval.fetch && .venv/bin/python -I -m fineval.build
```

```bash
# 2. score the saved outputs (writes results/scores/<run>.json)
for r in qwen2.5-7b llama3.1-8b; do for t in closed tools; do .venv/bin/python -I -m fineval.score --run ${r}__concept_tagging__${t}__s0; done; done
```

```bash
# 3. rebuild the page data (asserts equality with results/scores), then serve demo/
PYTHONUTF8=1 .venv/bin/python scripts/build_demo.py && cd demo && python3 -m http.server 8765
```

Other commands:

| Command | What it does |
|---|---|
| `python -I -m fineval.run --model ollama:<tag> --task concept_tagging --track <t>` | New run. The tracks are `closed`, `tools` (tag search filtered to the item's given type, an **oracle diagnostic**), `tools_noorac` (no type information) and `tools_numeric` (numeric types only). |
| `bash scripts/run_next_stage.sh` | All next-stage runs, profiles and the scorer check. Resumable. |
| `python -I scripts/profile_runs.py --model ollama:<tag> --track <t>` | Latency and peak memory on 100 fixed FinCL items. |
| `python -I scripts/scorer_check_fincl.py` | Compares our scorer with FinTagging's official one. |
| `python -I scripts/verify_demo_page.py <page_text.txt>` | Checks every number on the page against the raw files. |
| `python -I scripts/versions.py` | Writes `docs/VERSIONS.md`: code, data, model and runtime versions. |

Set `FINEVAL_RESULTS=results/mac/<chip>` (or any folder) to keep a second machine's runs apart from
the committed ones.

## Build

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.lock.txt && .venv/Scripts/python -m pip install -e .
.venv/Scripts/python -I -m fineval.fetch       # download pinned sources, check SHA-256
.venv/Scripts/python -I -m fineval.build       # load, de-duplicate, split -> data/v1/
.venv/Scripts/python -I -m fineval.datasheet   # docs/datasheet.md
.venv/Scripts/python -I -m pytest -q           # all exit tests
```

## Layout

```
fineval/sources/   registry.py (pinned sources), loaders.py (raw file -> unified records)
fineval/           schema, normalize, dedup, splits, build, data (subsets + leakage-safe few-shot)
reference/         published.json: published scores with paper, page and table
review/            near_dups.csv: near-duplicate pairs for a human join/separate decision
data/v1/           built benchmark (rebuilt, not committed) + summary/overlap/conflict files
tests/             exit tests for every phase
```
