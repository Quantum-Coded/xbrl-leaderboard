# Reproducing the results (technical)

The plain-language overview is in the [README](../README.md). This page has every command.

## XBRL Leaderboard: reproduce in 3 commands

Saved model outputs are committed in `results/generations/`, so no GPU is needed to check the
numbers. On Windows, replace `.venv/bin/python` with `.venv/Scripts/python`.

```bash
# 1. setup: environment, pinned data (SHA-256 checked), deterministic build
python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.lock.txt && .venv/bin/python -m pip install -e . && .venv/bin/python -I -m fineval.fetch && .venv/bin/python -I -m fineval.build
```

```bash
# 2. score the saved outputs (writes results/scores/<run>.json)
for f in results/scores/*__s0.json; do r=$(basename "$f" .json); case $r in *filing_qa*) continue;; esac; .venv/bin/python -I -m fineval.score --run "$r" > /dev/null; done
```

```bash
# 3. rebuild the page data (asserts equality with results/scores), then serve demo/
PYTHONUTF8=1 .venv/bin/python scripts/build_demo.py && cd demo && python3 -m http.server 8765
```

What to expect (checked on macOS, Apple M4):

- Command 2 rewrites every committed score file with no change: `git status` stays clean.
- Command 3 prints one line per run ending in `== stored score file`, and leaves `demo/data.js` unchanged.
- Open http://localhost:8765 to see the page.

To check the page itself, keep the server running, save the page's visible text with both tabs shown
(`?all`), and run the checker. It recomputes every number from the saved outputs and profile files and must
print `ALL NUMBERS ON THE PAGE MATCH THE RAW FILES.` `page_text.py` uses Edge or Chrome (set `BROWSER` to
its path if it is not found).

```bash
.venv/bin/python -I scripts/page_text.py http://localhost:8765/ results/audit/demo_page_text.txt
```

```bash
PYTHONUTF8=1 .venv/bin/python -I scripts/verify_demo_page.py results/audit/demo_page_text.txt
```

To run the test suite, build the training files first (the tests read them):

```bash
.venv/bin/python -I -m fineval.train_data && .venv/bin/python -I -m pytest -q
```

Versions, hosting and citation:

- [`docs/VERSIONS.md`](VERSIONS.md): our commit, the pinned data commits, model digests and runtime.
- [`docs/HOSTING.md`](HOSTING.md): how we propose to host the page.
- [`results/scorer_check/README.md`](../results/scorer_check/README.md): our scorer against FinTagging's official one.
- [`CITATION.cff`](../CITATION.cff): how to cite this repository and the datasets it uses.

Other commands:

| Command | What it does |
|---|---|
| `python -I -m fineval.run --model ollama:<tag> --task concept_tagging --track <t>` | New run. The tracks are `closed`, `tools` (tag search filtered to the item's given type, an **oracle diagnostic**), `tools_noorac` (no type information) and `tools_numeric` (numeric types only). |
| `bash scripts/run_next_stage.sh` | All next-stage runs, profiles and the scorer check. Resumable. |
| `python -I scripts/profile_runs.py --model ollama:<tag> --track <t>` | Latency and peak memory on 100 fixed FinCL items; add `--task financial_calc` (tracks `closed`, `tools`) for 100 fixed calculation items. Also records the peak GPU temperature. |
| `python -I scripts/safe_run.py --job <model>,<task>,<track> [--job ...]` | Runs jobs in chunks of 50 with pauses, a GPU temperature ceiling and a stop on the first failure (for laptops; `--dry-run` prints the plan). |
| `python -I scripts/profile_runs.py --model <m> --task financial_calc --track tools --pause-every 10 --pause 60 --cool-to 65` | Profile with a pause (and cool-down below 65 C) every 10 items; pauses are outside the timing. Used for the 7–8B calculation profiles. |
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
