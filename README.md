# FinEval v1

A reproducible benchmark for LLMs on financial reporting: XBRL concept tagging, fact extraction from
filings, financial calculation and filing QA. It combines FinTagging, XBRL-Agent, FinanceBench and the
COLING 2025 Regulations Challenge, removes cross-source duplicates, and keeps published scores apart
from scores reproduced under one common setup.

* Scope and rationale: [`PLAN.md`](PLAN.md)
* Phase-by-phase plan with exit tests: [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md)
* What is in the data, overlaps and conflicts: [`docs/datasheet.md`](docs/datasheet.md) (generated)

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
