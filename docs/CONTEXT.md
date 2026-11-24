# Project context and current state (18 Nov 2026)

One file to get up to speed. It covers what the project is, what is done, where everything is, and every
verified number. Next steps for Stavan are in [`HANDOFF.md`](HANDOFF.md).

## 1. The project in five lines

- **Name:** XBRL Leaderboard. Supervisor: Prof. Xiao-Yang (Yanglet) Liu. Team: Dev Gaglani (Windows
  laptop, evaluation lead) and Stavan Desai (Apple M4 Mac, page lead).
- **Question:** what can small open-weight models (1.5B–8B) do on XBRL tasks on an ordinary laptop,
  where do they fail, and what does each answer cost in time and memory?
- **Why:** firms want models they can run in-house. Belcak et al. (arXiv 2506.02153) argue small
  models suit narrow agent tasks, but say task-specific benchmarks are missing. XBRL tagging is such a
  task.
- **Output:**
  - a public static page (`demo/`);
  - the code and every saved model answer (repository
    https://github.com/Quantum-Coded/xbrl-leaderboard, MIT for the code);
  - a 2-page proposal (`proposal/proposal.pdf`).
- **Later:** a small change to the group's Open FinLLM Leaderboard (FINOS) so it can show XBRL tasks.

## 2. Timeline so far

| Date | What happened |
|---|---|
| 26 Oct | Prof. Liu's first request |
| 12 Nov | He asks for a focused 2-page proposal |
| 15 Nov | He reframes it as the "XBRL Leaderboard": one task, two models, a simple working page |
| 15 Nov | Proposal v4 and the first demo page (now in `proposal/archive/`) |
| 16 Nov | His second feedback: small open-weight models, label the oracle, report accuracy + latency + peak memory, reuse the group's evaluation code, calculation next, simple hosting |
| 16–17 Nov | Stavan: oracle labels, scorer check notes, Mac runs and profiles, hosting plan, citation. Dev: no-oracle and numeric conditions, profiler, versions |
| 17–18 Nov | Dev: all Windows runs and profiles, four extra models, calculation, page v2, proposal v5, Pages workflow, these docs |
| 23–24 Nov | Dev: last three calculation runs with `safe_run.py` (all seven models on the page), calculation profiles for four models |

## 3. Tasks and conditions

**Concept linking (FinCL).** Link one number from an SEC filing to the right US-GAAP concept (17,388
concepts in the 2024 taxonomy).

- **Data:** the FinTagging public subset. 500 items are released, 491 remain after removing
  duplicates, and 484 are scored after excluding conflicting answers. Every removed item is listed in
  `data/v1/`.
- **Metric:** exact match on the concept (`concept_exact@v1`), with 95% bootstrap intervals (2,000
  resamples, seed 0).
- **Conditions** (`fineval/prompts.py`), all with 100 candidates from BM25 except No tools:

| Key | Page label | What it does |
|---|---|---|
| `closed` | No tools | The model answers from memory |
| `tools_noorac` | Search | BM25 over all concepts, no type information |
| `tools_numeric` | Search + numeric | BM25 limited to a fixed list of 13 numeric XBRL types (`fineval/tools.py` `NUMERIC_TYPES`, taken from the taxonomy, not the test set) |
| `tools` | Search + oracle type | BM25 limited to the item's given type. The given type equals the gold concept's type on all 484 items (asserted in `build_demo.py`), so this is an **oracle diagnostic**, never ranked |

**Financial calculation.** 1,000 formula questions from XBRL-Agent (50 named formulas). Correct means a
number in the final part of the answer is within 1% of the gold value (`numeric_match@v1`).

- **No tools:** the model works the answer out in text.
- **Tools:** BM25 finds a formula (the right one for 844 of 1,000 questions), the model writes one
  arithmetic expression, and a safe calculator evaluates it.

**Setup.**

- Ollama, 4-bit quantisation, greedy decoding, seed 0. All models are Q4_K_M except Gemma-2-2B, which
  is Q4_0.
- Exact digests and versions are in `docs/VERSIONS.md`.
- **Windows:** RTX 4050 Laptop 6 GB, i5-13420H, 16 GB. Runs before 17 Nov used Ollama 0.40.15; runs
  from 17 Nov used 0.40.16. Each run's meta file records its version.
- **Mac:** Apple M4, 16 GB, Ollama 0.40.16.

## 4. Verified numbers

Every number below is on the page or in a committed file. `build_demo.py` rescores each run from its
saved answers and asserts that the result equals its score file. `verify_demo_page.py` recomputes
every number on the page from the raw files.

### 4.1 Linking accuracy, Windows (correct of 484)

| Model | No tools | Search | Search + numeric | Search + oracle type |
|---|---|---|---|---|
| Qwen2.5-7B | 6 (1.2%) | 61 (12.6%) | 71 (14.7%) | 75 (15.5%) |
| Llama-3.1-8B | 8 (1.7%) | 58 (12.0%) | 65 (13.4%) | 75 (15.5%) |
| Qwen2.5-3B | 5 (1.0%) | 50 (10.3%) | 57 (11.8%) | 59 (12.2%) |
| Llama-3.2-3B | 3 (0.6%) | 44 (9.1%) | 52 (10.7%) | 56 (11.6%) |
| Mistral-7B | 0 (0.0%) | 46 (9.5%) | 44 (9.1%) | 55 (11.4%) |
| Qwen2.5-1.5B | 8 (1.7%) | 39 (8.1%) | 44 (9.1%) | 47 (9.7%) |
| Gemma-2-2B | 3 (0.6%) | 43 (8.9%) | 39 (8.1%) | 43 (8.9%) |

- **Stability:**
  - every run has 581 answers with status `ok`;
  - our parser reads all 484 scored answers in every run except Mistral-7B with no tools (480 of 484).
- **Published reference** (FinTagging paper, Table 8, full gated set, their own retriever): GPT-4o
  18.3%, Llama-3.1-8B 9.1%. These are not directly comparable with our runs.

### 4.2 Why models fail (retrieval vs selection)

- **Retrieval.** The gold concept is among the 100 candidates for 134 of 484 items (27.7%) with Search,
  151 (31.2%) with numeric types, and 171 (35.3%) with the oracle type. This depends only on the search,
  not on the model.
- **Selection.** When the gold concept is a candidate, the model picks it:

| Model | Search | Search + numeric | Search + oracle type |
|---|---|---|---|
| Qwen2.5-7B | 60 of 134 (44.8%) | 71 of 151 (47.0%) | 75 of 171 (43.9%) |
| Llama-3.1-8B | 57 of 134 (42.5%) | 65 of 151 (43.0%) | 75 of 171 (43.9%) |
| Qwen2.5-3B | 49 of 134 (36.6%) | 56 of 151 (37.1%) | 58 of 171 (33.9%) |
| Llama-3.2-3B | 44 of 134 (32.8%) | 51 of 151 (33.8%) | 55 of 171 (32.2%) |
| Mistral-7B | 46 of 134 (34.3%) | 44 of 151 (29.1%) | 55 of 171 (32.2%) |
| Qwen2.5-1.5B | 39 of 134 (29.1%) | 44 of 151 (29.1%) | 47 of 171 (27.5%) |
| Gemma-2-2B | 43 of 134 (32.1%) | 39 of 151 (25.8%) | 43 of 171 (25.1%) |

### 4.3 Cost per answer (100 fixed items, plugged in, after one warm-up)

Source: `results/profile/rtx-4050-laptop-gpu/` (Windows) and `results/mac/m4/profile/m4/` (Mac). Never
mix the two machines.

**Windows** (NVIDIA GeForce RTX 4050 Laptop GPU, Ollama 0.40.16). Median seconds per item, memory in MiB.

| Model | No tools | Search | Search + oracle type | Model in memory | GPU peak |
|---|---|---|---|---|---|
| Qwen2.5-1.5B | 0.21 s | 0.53 s | 0.53 s | 1,115 | 1,224 |
| Gemma-2-2B | 0.31 s | 0.90 s | 0.92 s | 1,836 | 2,156 |
| Qwen2.5-3B | 0.28 s | 0.79 s | 0.85 s | 2,063 | 2,172 |
| Llama-3.2-3B | 0.26 s | 0.88 s | 0.93 s | 2,442 | 2,546 |
| Qwen2.5-7B | 0.44 s | 1.57 s | 1.60 s | 4,535 | 4,648 |
| Mistral-7B | 0.52 s | 2.12 s | 2.14 s | 4,729 | 4,838 |
| Llama-3.1-8B | 0.66 s | 1.82 s | 1.96 s | 5,035 | 5,144 |

**Mac** (Apple M4, Ollama 0.40.16). Median seconds per item, memory in MiB.

| Model | No tools | Search | Search + oracle type | Model in memory |
|---|---|---|---|---|
| Qwen2.5-3B | 1.04 s | 8.53 s | 9.06 s | 2,063 |
| Qwen2.5-7B | 1.52 s | 17.43 s | 15.65 s | 4,535 |
| Llama-3.1-8B | 1.50 s | 20.51 s | 21.87 s | 5,035 |

- **Windows:** every model fits fully on the 6 GB GPU (Ollama `size_vram` equals `size` in every
  profile).
- **Mac:**
  - also fully on the shared GPU memory;
  - prompt reading is slow, which explains most of the tag-search time (about 2,000 prompt tokens per
    item);
  - process memory (RSS) is not reported because the model files are memory-mapped.

### 4.4 Mac vs Windows accuracy (same prompts, same model files)

| Model | No tools | Search | Search + oracle type |
|---|---|---|---|
| Qwen2.5-3B | 1.0% (Win 1.0%) | 9.7% (Win 10.3%) | 11.8% (Win 12.2%) |
| Qwen2.5-7B | 1.4% (Win 1.2%) | 12.8% (Win 12.6%) | 14.9% (Win 15.5%) |
| Llama-3.1-8B | 1.4% (Win 1.7%) | 11.8% (Win 12.0%) | 14.7% (Win 15.5%) |

Every Mac score is inside the Windows 95% interval. `verify_demo_page.py` asserts this. Raw outputs are
not byte-identical across machines; details are in `results/mac/m4/README.md`.

### 4.5 Calculation, Windows (correct of 1,000)

| Model | No tools | Formula lookup + calculator |
|---|---|---|
| Qwen2.5-7B | 657 (65.7%) | 764 (76.4%) |
| Llama-3.1-8B | 603 (60.3%) | 732 (73.2%) |
| Llama-3.2-3B | 553 (55.3%) | 668 (66.8%) |
| Gemma-2-2B | 382 (38.2%) | 597 (59.7%) |
| Qwen2.5-3B | 603 (60.3%) | 561 (56.1%) |
| Mistral-7B | 555 (55.5%) | 496 (49.6%) |
| Qwen2.5-1.5B | 669 (66.9%) | 301 (30.1%) |

- **Units.** The metric is strict about units: a rate written as 5 instead of 0.05 counts as wrong.
  Without tools, the 3B–8B models lose many points this way. Ignoring units (the `unit_agnostic`
  variant in each score file):

| Model | No tools, ignoring units | With tools, ignoring units |
|---|---|---|
| Qwen2.5-7B | 81.1% | 78.3% |
| Llama-3.1-8B | 70.9% | 74.8% |
| Llama-3.2-3B | 63.3% | 70.8% |
| Gemma-2-2B | 51.3% | 61.3% |
| Qwen2.5-3B | 75.7% | 60.2% |
| Mistral-7B | 57.9% | 55.4% |
| Qwen2.5-1.5B | 68.4% | 34.4% |

- **Tools help four models and hurt three.** They help Qwen2.5-7B, Llama-3.1-8B, Llama-3.2-3B and
  Gemma-2-2B. They hurt Qwen2.5-3B, Mistral-7B and Qwen2.5-1.5B, which often write an expression the
  calculator cannot evaluate. Counts of 1,000 tools answers (recomputed with
  `prompts.finish_tools_calc`):

| Model | Expression fails to evaluate | No expression |
|---|---|---|
| Qwen2.5-1.5B | 354 | 166 |
| Mistral-7B | 302 | 0 |
| Gemma-2-2B | 240 | 1 (the server-error item) |
| Qwen2.5-3B | 91 | 0 |
| Qwen2.5-7B | 89 | 0 |
| Llama-3.2-3B | 63 | 0 |
| Llama-3.1-8B | 62 | 1 |

- All seven models are on the page since 24 Nov.

### 4.6 Scorer check against FinTagging's official code

`scripts/scorer_check_fincl.py` → `results/scorer_check/fincl.json`. The official code is
`evaluate_NEN.ipynb` at FinTagging `ff426bc`.

- **Six of the seven models:** identical item for item under all four conditions.
- **Llama-3.1-8B, the exception:** its three tag-search runs differ, because it writes pretty-printed
  JSON. Correct of 484 (items that differ in brackets):

| Condition | Ours | Official |
|---|---|---|
| Search | 58 | 32 (30) |
| Search + numeric | 65 | 39 (32) |
| Search + oracle type | 75 | 39 (40) |

- Llama-3.1-8B with no tools: identical.
- The full table is in `results/scorer_check/README.md`.

- The official parser needs `{"result"` with no whitespace. When it fails, it falls back to the first
  candidate.
- We report our scorer and note the official number.
- No FinCL scorer exists in the public FinBen or leaderboard repositories (searched 16 Nov). That is an
  open question for Prof. Liu.

## 5. Where everything is

| What | Where |
|---|---|
| Plain-language overview | `README.md` |
| Every command | `docs/REPRODUCE.md` |
| Method and checks | `docs/protocol.md`, `docs/datasheet.md` |
| Page | `demo/index.html` + `demo/data.js`, built by `scripts/build_demo.py`, checked by `scripts/verify_demo_page.py` (text from `scripts/page_text.py`) |
| Run scripts | `scripts/run_next_stage.sh`, `scripts/run_extra_models.sh` (`PROFILE_ONLY=1` for profiles only), `scripts/run_extra_calc.sh`; `scripts/safe_run.py` for long GPU runs on a laptop (chunks, pauses, temperature ceiling) |
| Profiler | `scripts/profile_runs.py` (FinCL or `--task financial_calc`; refuses to run on battery; records peak GPU temperature) |
| Saved answers and scores | `results/generations/`, `results/scores/` (Windows); `results/mac/m4/` (Mac) |
| Versions | `docs/VERSIONS.md` (regenerate on Windows: `python -I scripts/versions.py`) |
| Hosting | `docs/HOSTING.md`, `.github/workflows/pages.yml` |
| FINOS | `docs/FINOS_INTEGRATION.md` (analysis), `docs/FINOS_ISSUE_DRAFT.md` (issue text, not opened) |
| Proposal | `proposal/proposal.tex` → `proposal.pdf` (built with tectonic); old versions in `proposal/archive/` |
| Citation, licence | `CITATION.cff`, `LICENSE` (MIT, code only; data keeps its sources' licences) |

**Never commit:**
- FinanceBench data or outputs (CC-BY-NC; `*filing_qa*` is gitignored);
- Prof. Liu's documents (`docs/references/`, gitignored);
- any secrets.

## 6. Hosting status

- **Live since 18 Nov 2026 (source "GitHub Actions"):** https://quantum-coded.github.io/xbrl-leaderboard/
  - The workflow `.github/workflows/pages.yml` republishes `demo/` on every push to `master` that
    changes `demo/`.
  - The repository was already public, so the page exposes nothing new.
- **The link has not been sent to Prof. Liu.** That waits for both of us to agree (`docs/HOSTING.md`).
- After each publish, run `scripts/page_text.py` on the live address, then `verify_demo_page.py`.

## 7. Open questions (for Prof. Liu)

1. Is there a FinTagging task file in the group's evaluation suite that we should use instead of
   FinTagging's own code?
2. Should the page stay in our repository or move under the group's organisation, and who reviews
   changes?
3. Which task comes second: XBRL-Agent terminology or FinAuditing?
4. Which code and dataset run the public FINOS Space (the repository loads `TheFinAI/greek-contents`)?

## 8. Known limits

- **Calculation profiles: four of seven models.** Speed and memory for calculation (100 items, no tools
  and with tools) exist for Qwen2.5-1.5B, Gemma-2-2B, Qwen2.5-3B and Llama-3.2-3B
  (`results/profile/rtx-4050-laptop-gpu/*__financial_calc__*`). The laptop restarted unexpectedly at
  22:21 on 23 Nov (Windows Kernel-Power event 41) during the Qwen2.5-7B profile, which runs 100 items
  without pauses. Qwen2.5-7B, Mistral-7B and Llama-3.1-8B are not profiled, and the page shows no
  calculation cost until all seven are.
- **Calculation runs finished on 23 Nov with `scripts/safe_run.py`.** Long unbroken GPU runs had led to
  restarts on 18 Nov, so the last runs (Gemma-2-2B with tools from 852, Llama-3.2-3B no tools from 735,
  Mistral-7B both) ran in chunks with a 60 s pause, waiting below 65 C before each chunk. The GPU reached
  80 C, so chunks shrank from 50 to 10 items. Results are identical to one long run, because the runner
  resumes.
- **One server error.** Gemma-2-2B with tools: Ollama fails on item `xbrl_agent:formula:test:47-20` (a
  Black-Scholes question) on every retry, after about 128 generated tokens. `fineval/run.py` records it as
  `server_error`; it counts as wrong and is listed in the score file's status.
- **Mixed Ollama versions (11–12 Nov vs 17–18 Nov runs).** For Qwen2.5-3B, Qwen2.5-7B, Llama-3.1-8B
  and Mistral-7B:
  - the No tools runs (11 Nov) did not record the Ollama version;
  - the oracle-search runs (12 Nov) used 0.40.15;
  - their Search and Search + numeric runs (17–18 Nov) used 0.40.16.

  All other runs used 0.40.16. The model digests are the same throughout.
- Llama-3.1-8B calculation with no tools started on 0.40.15 and finished on 0.40.16 (it resumed at
  item 843).
- The Mac has full accuracy runs only for Qwen2.5-3B, Qwen2.5-7B and Llama-3.1-8B (three conditions).
- One seed only. Greedy decoding makes reruns on the same machine identical, but not across machines.
