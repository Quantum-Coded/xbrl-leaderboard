# XBRL Leaderboard: full handoff for Stavan

**Who this is for.** Stavan (and his Claude Code), on a Mac. After reading it you should be at exactly
the same point as Dev and able to carry on in parallel.

**How to use it.** Read the whole file once; it is long. Then do the steps in Section 8.
Sections 1–6 are context. Section 7 lists what to read. Section 8 is the work. Section 9 is Mac setup.

Last updated: 16 Nov 2026, at the commit that added this file.

---

## 0. Ground rules

These apply to both of us and to both our Claudes. They are from `IMPLEMENTATION_PLAN.md`, Section 0.

1. **No number without a file behind it.**
   - Every count, score and published figure on the page, in the proposal or in an email comes from a
     file in the repo.
   - Each must be re-checkable by a script.
   - Never estimate, round in a way that changes meaning, or type a number from memory.
2. **Every source is pinned** to a commit or revision, with its SHA-256 in `data/raw/MANIFEST.json`.
3. **Unverified means labelled.** Anything not yet checked is marked `TO VERIFY` and never stated as a
   fact.
4. **Test data is never used for tuning.** This covers prompts, few-shot examples, filters, candidate
   counts and anything else.
5. **Deterministic runs:** greedy decoding, seed 0, model digest recorded.
6. **Downloads are untrusted data.**
   - Python that reads downloaded files runs with `-I`.
   - No pickle or `trust_remote_code` weights without asking.
7. **Git.**
   - Each of us works on our own branch.
   - No AI attribution lines in commits.
   - The repo https://github.com/Quantum-Coded/xbrl-leaderboard is **public** so that you can clone it.
     So never commit secrets, Prof. Liu's documents, or FinanceBench data or outputs (CC-BY-NC).
   - Push only to your own branch. `master` changes only when both of us agree.
8. **Writing for Prof. Liu** is short, plain and to the point.
   - Always **Reply all**, so that Dev, Stavan and the professor all stay on the thread.

---

## 1. The story so far

| When | What happened | Where it lives |
|---|---|---|
| From 17 Oct 2026 | **Task 1.** We reproduced the COLING-2025 Regulations Challenge (arXiv 2412.11159) locally. We rebuilt the unpublished scorer and calibrated it against the paper. We found 95 validation items leaking into test. We kept "paper" and "ours" scores apart. We audited the LLM judge against human labels. We showed that tools help small models more than fine-tuning. | Separate repo `research-intern/regulations-challenge/` (GitHub `Quantum-Coded/llm-finance`) |
| 26–29 Oct | Prof. Liu (26 Oct email) asked us to review the resources and propose a manageable first version. He asked for overlapping questions to be handled, and for published scores to be kept apart from reproduced ones. We wrote `PLAN.md`, which combines 5 sources and measures the overlap between them. | `PLAN.md`, `overlap_check.py` |
| Late Oct to early Nov | We built the benchmark harness, phases 0–10 in `IMPLEMENTATION_PLAN.md`. | `fineval/`, `tests/`, `site/` (an early React site, now superseded by `demo/`), `report/`; git history `d5f84ea` to `5193313` |
| Early to mid Nov | He asked for a focused 2-page proposal. Version 3 asked how much FinCL error comes from **retrieval vs selection**. It went through two reviewer passes and gained the type-filter analysis. | `proposal/archive/proposal_v3_retrieval_or_selection.*`, `scripts/type_filter_coverage.py` |
| 15 Nov | **Reframe.** Prof. Liu sent `XBRL_Leaderboard_Student_Guide.pdf`. The project is now the **XBRL Leaderboard**: one task, two models, a simple working page, and retrieval vs selection kept only as the failure analysis. We should reuse the group's resources. We built the minimal demo page, a script that checks every number on it, and a new 2-page proposal with a screenshot. | `demo/`, `scripts/build_demo.py`, `scripts/verify_demo_page.py`, `proposal/proposal.{tex,pdf}`, `proposal/demo_screenshot.png` |
| 16 Nov | **Second feedback from Prof. Liu** on that proposal. It drives the plan below (Section 5). | This file |

The website design reference is **conductbenchmark.com** (FinCon Bench): a dark theme, one clear
question, a bar ranking, a worked example and insight cards. Its code is at
`github.com/Doshi-App/fincon-bench`.

---

## 2. What the repo contains

```
fineval/          the harness
  fetch.py        download pinned sources, check SHA-256  -> data/raw/ (gitignored, re-downloaded)
  build.py        load, de-duplicate, split               -> data/v1/  (rebuilt deterministically)
  prompts.py      prompts per task and track; tag search is here (line 46, TAG_CANDIDATES=100)
  tools.py        BM25 taxonomy search, formula search, filing search, calculator
  llm.py          Ollama backend (OLLAMA_HOST_URL, FINEVAL_NUM_GPU), digest + runtime version
  run.py          resumable generation -> results/generations/<model>__<task>__<track>__s<seed>.jsonl
  score.py        scoring -> results/scores/*.json; scorers.py has one versioned scorer per task
  stats.py        bootstrap CIs, paired bootstrap
  feasibility.py  throughput + VRAM probe (NVIDIA only)
scripts/
  build_demo.py           rescore 4 FinCL runs, assert equal to results/scores, write demo/data.js
  verify_demo_page.py     recompute every number from raw files; check the page text against them
  type_filter_coverage.py BM25 coverage of the gold concept under different type filters
  run_batch.sh            Dev's Windows batch script (uses .venv/Scripts; do not use on Mac)
demo/             index.html + data.js: the current page (served with python -m http.server)
proposal/         proposal.tex/.pdf (current, 2 pages), demo_screenshot.png, archive/ (v3)
results/          generations/ (model outputs), scores/, retrieval/, audit/, logs/, feasibility.json
docs/             datasheet.md (generated), protocol.md (how every number is produced), this file
reference/        published.json: published scores with citation, page and table
PLAN.md, IMPLEMENTATION_PLAN.md   original scope and phase plan with exit tests
```

**Not in git; you rebuild these.**
- `data/raw/` and `data/v1/test|train|validation`. Rebuild them with fetch and build (Section 9).
- `models/`: Dev's QLoRA weights, 5.8 GB, not needed.
- `results/generations/*filing_qa*`. These are FinanceBench-derived outputs, and FinanceBench is
  CC-BY-NC, so they stay out of this public repo.
- Prof. Liu's `XBRL_Leaderboard_Student_Guide.pdf`. It is his document, so it is not in the public
  repo; you have it from his email, or Dev can forward it.

All other model outputs **are** committed, so the demo can be rebuilt and checked without a GPU.

---

## 3. The task and the setup (the current page)

**Task: FinCL concept linking.** FinTagging has two subtasks. FinNI finds the numbers in a filing.
FinCL, the one we use, links one number to the right US-GAAP 2024 concept.

**Input.** A number, its context (a filing table row or sentence) and its item type, for example
`monetaryItemType`.

**Output.** One concept out of **17,388** (`us_gaap_2024_BM25.jsonl`).

**Items.**
- FinTagging's public FinCL subset releases **500** items.
- **491** remain after merging duplicates.
- **7** have the same input but different gold answers. They are excluded as ambiguous.
- **484** are scored, of which 451 are table rows.
- Every removed item is listed in `data/v1/`. The counts are in `data/v1/summary.json`:
  11,401 records loaded and 10,457 clusters across all sources.

**Models.** All run through Ollama 0.40.15, with greedy decoding and seed 0.

| Ollama tag | Quantisation | Digest prefix |
|---|---|---|
| `qwen2.5:7b` | 4-bit Q4_K_M | `845dbda0ea48` |
| `llama3.1:8b` | 4-bit Q4_K_M | `46e0c10c039e` |
| `qwen2.5:3b` | 4-bit Q4_K_M | `357c53fb659c` |
| `mistral:7b` | — | — |

Mistral was run in the early harness but is not on the page.

**Conditions.**
- `closed`: no tools.
- `tools`, called **tag search** on the page:
  - BM25 over the taxonomy returns the top 100 candidates (`TAG_CANDIDATES=100`), which go into the
    prompt.
  - The search is **filtered to concepts of the item's given type** (`prompts.py:46`,
    `entity_type=inp["entity_type"]`).
  - That given type always equals the gold concept's type. So **this condition is an oracle
    diagnostic**: it uses information a real system would not have.
- FinTagging's own released search adds the type to the query text. That is a soft boost, not a hard
  filter.

**Scoring.** Exact match with the gold concept (`concept_exact@v1`), with 95% bootstrap CIs.

---

## 4. Verified numbers

Every number below is computed from a file. `scripts/verify_demo_page.py` checks each one on the page.

**FinCL subset (484 items).** Sources: `results/scores/*concept_tagging*.json` → `by_subset.fincl_subset`,
and `demo/data.js`.

| Model | No tools | Tag search (oracle type) |
|---|---|---|
| Qwen2.5-7B | 1.2% (6), CI [0.4, 2.3] | 15.5% (75), CI [12.2, 18.8] |
| Llama-3.1-8B | 1.7% (8), CI [0.6, 2.9] | 15.5% (75), CI [12.4, 19.0] |
| Qwen2.5-3B | 1.0% | 12.2% |

- **Paired gain from tag search:** +14.3 points [11.2, 17.6] for Qwen-7B and +13.8 [10.5, 17.1] for
  Llama.
- **Why models fail.**
  - Search puts the gold in the 100 candidates for 171 of 484 items (**35.3%**).
  - When the gold is there, each model picks it for 75 of those 171 (**43.9%**).
  - No correct answer comes from outside the candidate list.
- **Coverage without the oracle**, from `results/retrieval/type_filter_coverage.json`. Values are
  coverage at 100 / at 200 candidates.

  | Type filter | @100 | @200 |
  |---|---|---|
  | None | 27.7% | 31.2% |
  | Numeric types only | 31.2% | 35.5% |
  | Soft boost from the given type | 31.4% | 36.8% |
  | Given type (oracle) | 35.3% | 41.5% |

  - The numeric list is fixed from XBRL 2.1 and the Data Type Registry, not from test items.
  - Most of the oracle's gain comes from the 51 non-monetary items.
  - **End-to-end accuracy without the oracle has not been run yet.**
- **Published reference, not comparable.** The FinTagging paper (arXiv 2505.20650v5, Table 8, FinCL
  column, full gated test set) reports:
  - GPT-4o 0.1829;
  - Llama-3.1-8B-Instruct 0.0913.
- **Other tasks already run.** These are in `results/scores/`. They are not on the page, and their
  item counts differ.

  | Task | Metric | Item count | Qwen2.5-7B | Llama-3.1-8B | Mistral-7B | Qwen2.5-3B |
  |---|---|---|---|---|---|---|
  | Concept tagging, all subsets | Exact match | 574 | 3.1% closed, 18.8% tools | 1.6% closed, 17.9% tools | 0.2% closed, 11.8% tools | 2.3% closed, 14.5% tools |
  | Fact extraction (FinNI) | Strict F1 | 199 | 44.5% | 38.0% | 33.2% | 22.5% |
  | Financial calculation (XBRL-Agent) | Final answer | 1000 | — | — | — | 60.3% closed [57.3, 63.3], 56.1% tools [53.0, 59.3] |

  The Llama calculation run with no tools stopped at 843 of 1000 items and is not scored.
- **Latency and memory: not yet reportable.**
  - Per-item latency is saved in the generations (`latency_s`). Median seconds per item, no tools /
    tag search:

    | Model | No tools | Tag search |
    |---|---|---|
    | Qwen2.5-3B | 0.45 | 0.86 |
    | Qwen2.5-7B | 0.55 | 1.65 |
    | Llama-3.1-8B | 0.65 | 1.95 |

    These came from a batch that ran on battery and hit a thermal sleep, so **do not report them**.
  - Peak memory was not recorded per run. The only figure is a one-off probe in
    `results/feasibility.json`: llama3.1:8b used 4885–5659 MiB of VRAM.

---

## 5. Prof. Liu's latest feedback (16 Nov), point by point

| His point | What it means for us | Who |
|---|---|---|
| **Reply all** so both of us stay copied | Always reply to the whole thread | Both |
| Focus on **open-weight, small models for internal deployment**; read arXiv 2506.02153 | Frame the leaderboard as "what small local models can do on XBRL, and at what cost" | Both |
| Keep the baselines; add one **smaller** model; report **accuracy, latency and peak memory** under the same hardware and inputs; no large models or API credits needed | Qwen2.5-3B is already run. We need a controlled timing and memory harness and a clean re-run. Drop "credits for >8B" from the help list. | Dev runs the harness; Stavan adds a Mac profile |
| Does tag search use the given type? If so, **label it an oracle diagnostic** | Yes, it does. Relabel it on the page and in the proposal, and add a **no-oracle** condition. | Dev (runs), Stavan (page) |
| Share a **demo link or runnable code**, with saved outputs and the scoring command | Package the repo and propose hosting | Stavan |
| **Reuse the group's evaluation code**; keep the FINOS integration small; **calculation is next** | Cross-check our scorer against FinTagging's official evaluation code. Make the FINOS change small. Calculation is the next task. | Stavan (cross-check), Dev (calculation) |
| The **public FinTagging subset is enough**; state the exact **code versions**; suggest **simple hosting** | Drop "gated test set access" from the help list. Write down the commits. Propose GitHub Pages. | Both |

**The paper (Belcak et al., NVIDIA, "Small Language Models are the Future of Agentic AI").**

- **Definition.** A small model fits on a common consumer device and serves one user with practical
  latency, roughly under 10B parameters today.
- **Position.**
  - Small models are already powerful enough for most agent calls (V1).
  - They are operationally more suitable (V2).
  - They are much cheaper (V3).
  - Agents mostly make narrow, repetitive calls with strict formats, so a mixed system makes sense:
    small models by default, large models only when needed.
- **Barriers.** It names three:
  - infrastructure already invested in large models (B1);
  - **benchmarks that are generalist rather than task-specific (B2)**;
  - lack of awareness (B3).
- **Conversion recipe (S1–S6):**
  1. log the agent's calls;
  2. curate the data;
  3. cluster it into recurring tasks;
  4. pick a small model by capability, licence and footprint;
  5. fine-tune with LoRA or QLoRA;
  6. iterate.
- **Our angle.**
  - XBRL tagging is exactly the kind of narrow, strictly formatted, repeated task the paper means.
  - The paper argues but does not measure, and B2 says task-specific measurement is missing.
  - The XBRL Leaderboard supplies that measurement for one finance domain: where 3–8B local models
    already work, where they fail (retrieval vs selection), and what they cost in latency and memory.
  - Later, if Prof. Liu wants it, the S4–S5 step (QLoRA on the train split) maps onto Dev's existing
    QLoRA scripts.

---

## 6. Open questions and known gaps

- **Scorer.** We score with our own scorer (`concept_exact@v1`). It has not yet been checked against
  FinTagging's official evaluation code.
- **Oracle labelling.** The page and proposal do not yet say "oracle"; that is fixed in step S1.
- **Timing and memory.** Latency and memory are not controlled yet; that is fixed in step D2.
- **Mac comparability.** On a Mac, Metal kernels and unified memory differ from NVIDIA. Mac accuracy
  should match Windows closely, but timing and memory **must never be mixed** with Windows numbers.
- **Help list.** The proposal's "Where we need help" still lists gated test access and >8B credits.
  Both have now been answered, so remove them in the next proposal revision.

---

## 7. Read these (in this order)

**Files in the repo.**

1. This file.
2. `proposal/proposal.pdf`: the current 2-page proposal, the version Prof. Liu commented on.
3. `XBRL_Leaderboard_Student_Guide.pdf`: Prof. Liu's guide, from his 15 Nov email. It is not in the
   repo. It is in Dev's reference zip (`xbrl_leaderboard_refs.zip`), along with his emails word for word;
   unzip it into `docs/references/`, which is gitignored.
4. `demo/index.html` (run it, Section 9) and `scripts/build_demo.py`, `scripts/verify_demo_page.py`.
5. `fineval/prompts.py`, `fineval/tools.py`, `fineval/run.py`, `fineval/score.py`, `fineval/scorers.py`.
6. `docs/protocol.md`: how every number is produced and checked.
7. `PLAN.md` and `IMPLEMENTATION_PLAN.md`: the original scope and phases, for background.
8. `proposal/archive/proposal_v3_retrieval_or_selection.pdf`: the earlier research question, for
   background.

**Papers.**

- Small language models (the motivation): https://arxiv.org/abs/2506.02153 (HTML: https://arxiv.org/html/2506.02153)
- FinTagging (the task; Table 8 is our reference): https://arxiv.org/abs/2505.20650 (v5 HTML: https://arxiv.org/html/2505.20650v5)
- FinAuditing (a later task): https://arxiv.org/abs/2510.08886
- Open FinLLM Leaderboard (hosting target): arXiv 2501.10963
- Evaluation and benchmarking suite for financial LLMs and agents: https://arxiv.org/abs/2602.19073
  (most likely the "FinAI Evals Suite" that Prof. Liu's 15 and 16 Nov emails call the group's
  evaluation code; TO VERIFY)
- FinBen (group evaluation code): arXiv 2402.12659, https://huggingface.co/papers/2402.12659
- COLING-2025 Regulations Challenge (our Task 1): https://arxiv.org/abs/2412.11159
- XBRL Agent: Han et al., ICAIF 2024. The code is below.

**Code and data, at the pinned versions.**

- FinTagging: https://github.com/The-FinAI/FinTagging @ `ff426bc4c914c3cc6d967a696fbc041ed157c459`
- FinTagging data on Hugging Face:
  - https://huggingface.co/collections/TheFinAI/fintagging-xbrl-tagging-68270132372c6608ac069bef
  - https://huggingface.co/datasets/TheFinAI/en-fincl-eval
  - https://huggingface.co/datasets/TheFinAI/en-finni-eval
- XBRL-Agent: https://github.com/KirkHan0920/XBRL-Agent @ `eafd6154f055058fcabcebc16868a0f877721def`
- Regulations Challenge: https://github.com/Open-Finance-Lab/Regulations_Challenge_COLING_2025 (the full
  commit is in `data/raw/MANIFEST.json`)
- FinanceBench (CC-BY-NC; keep it out of anything public): https://github.com/patronus-ai/financebench
- FinBen: https://github.com/The-FinAI/FinBen
- FINOS Open Financial LLM Leaderboard:
  - code: https://github.com/finos-labs/Open-Financial-LLMs-Leaderboard
  - Space: https://huggingface.co/spaces/finosfoundation/Open-Financial-LLM-Leaderboard
- Design reference: https://www.conductbenchmark.com (methodology page `/methodology`); code at
  https://github.com/Doshi-App/fincon-bench
- Ollama: https://ollama.com/download

---

## 8. Next stage: step-wise plan (in parallel)

### Ownership

| Dev (Windows, RTX 4050 6 GB) | Stavan (Mac) |
|---|---|
| `fineval/`, `scripts/run_batch.sh`, `scripts/profile_*.py`, `results/generations/`, `results/scores/` | `demo/`, `docs/` (except this file), `scripts/build_demo.py`, `scripts/verify_demo_page.py`, packaging and hosting, `results/mac/`, `results/scorer_check/` |

- If you need a change in the other person's files, message first; do not edit them.
- **Branches:** `dev/next` (Dev) and `stavan/next` (Stavan). We merge into `master` together at the end
  of the week.
- **Run names have no machine tag.** So Mac runs are **moved to `results/mac/<chip>/`** before
  committing, and never written into `results/generations/` or `results/scores/` in a commit.

### Step 1: reach Dev's state (Stavan, day 1)

1. Clone or pull the repo, check out `master`, then create `stavan/next`.
2. Do the Mac setup in Section 9.
3. `pytest` passes.
4. `data/v1/summary.json` shows `records_loaded: 11401` and `clusters: 10457`.
5. `build_demo.py` runs with no assertion errors. Its output `demo/data.js` must be byte-identical to
   the committed one; check with `git diff --stat`.
6. `verify_demo_page.py` prints "ALL NUMBERS ON THE PAGE MATCH THE RAW FILES."
7. The Ollama digests match the table in Section 3. If a tag now points to a newer file, stop and tell
   Dev; do not use a different model silently.

### Step 2: Dev's track (Windows GPU)

**D1. No-oracle condition.**
- In `prompts.py`, add a track `tools_noorac`, together with `TRACKS`:
  - it is the same as `tools`, except that `taxonomy_search` gets **no** `entity_type`;
  - optionally add a second variant restricted to numeric types, reusing `NUMERIC_TYPES` from
    `type_filter_coverage.py`.
- Add a test.
- Rename nothing in the existing runs: the old `tools` runs stay as the oracle diagnostic.

**D2. Profiling harness.**
- Add `scripts/profile_runs.py`. It runs a fixed list of items, the same for every model, after one
  warm-up call, and records per item:
  - wall latency;
  - Ollama `eval_count` and the eval and prompt durations;
  - **peak memory**:
    - Windows: poll `nvidia-smi` for GPU memory.
    - All machines: poll Ollama `GET /api/ps` (`size`, `size_vram`).
    - Mac: also sample the resident memory of the `ollama` runner process.
- It writes `results/profile/<machine>/<run>.json`, including:
  - the machine, OS, chip or GPU;
  - the Ollama version;
  - power state, which must be plugged in;
  - the model digest.
- It must work unchanged on the Mac. Dev pushes it early so Stavan can use it.

**D3. Clean runs, on Windows only.** Plugged in, nothing else on the GPU.
- Qwen2.5-3B, Qwen2.5-7B and Llama-3.1-8B, each under the 3 conditions: closed, tools (oracle) and
  tools_noorac.
- Results: accuracy, median and p90 latency, and peak memory.

**D4.** Score the runs, update `results/scores/`, and hand the numbers to Stavan for the page.

**D5 (next task).** Calculation (XBRL-Agent formulas, 1000 items) for the same three models, closed and
tools. First finish the Llama closed run that stopped at 843/1000.

### Step 3: Stavan's track (Mac)

**S1. Oracle labelling.**
- Relabel the tag-search rows as **"Tag search (given item type: oracle diagnostic)"**.
- Add a one-line explanation.
- Add space in the table for the no-oracle rows and for latency and memory columns.
- Update `verify_demo_page.py` so the new labels and numbers stay checked.
- Keep the page minimal: real values only, no decoration.

**S2. Reuse the group's evaluation code.**
- Prof. Liu's emails name the group's **FinAI Evals Suite**. First find its code repo, using the
  paper above, FinBen and the guide PDF, and check whether it has a FinTagging or FinCL task. If it
  does, use that. Otherwise use FinTagging's official FinCL evaluation code in the pinned repo.
- Run it, unchanged, on our saved outputs (`results/generations/*concept_tagging*`, FinCL items) and
  compare item by item with `scorers.concept_exact`.
- Write `results/scorer_check/fincl.json` and a short note. The note says either "identical on all 484
  items" or lists the exact differences and their cause.
- If they differ, propose switching to the official metric. Dev changes `fineval/`.

**S3. Mac reproducibility and a second hardware profile.**
- Run `qwen2.5:3b` closed and tools (oracle) on the Mac, and compare accuracy with Windows. It should
  be identical or very close; a difference is itself a finding.
- When D1 and D2 land, add `tools_noorac` and run the profiler.
- Save everything under `results/mac/<chip>/`, for example `results/mac/m2/`.
- Report the Mac separately, as its own hardware block.

**S4. Package and hosting proposal.**
- The demo is static (`demo/index.html` + `demo/data.js`).
- Propose **GitHub Pages** from this public repo (serving `demo/`), or a static Hugging Face Space as
  the alternative.
- Prepare a "reproduce in 3 commands" README section: setup, scoring command, build and verify the
  page.
- Write a `CITATION` and versions note listing:
  - our commit;
  - the FinTagging and XBRL-Agent commits;
  - the Ollama version;
  - the model digests.
- Check licences:
  - FinTagging: MIT code, CC-BY-4.0 data; attribution is fine.
  - FinanceBench: CC-BY-NC. Keep it **out**.
- **No link goes to Prof. Liu until both of us agree.**

**S5. FINOS integration, kept small.**
- Read `finos-labs/Open-Financial-LLMs-Leaderboard`. Write half a page on the smallest change that
  would add an XBRL tab: the task columns become a config entry, plus a tools field.
- Do not open a PR. Discuss it at the weekly meeting first.

### Step 4: merge and reply (both, end of week)

- Merge `dev/next` and `stavan/next` into `master`.
- Rebuild the page: models × conditions (closed / oracle / no-oracle), with accuracy, latency and peak
  memory. Windows and Mac are shown as separate blocks.
- Re-run `verify_demo_page.py`.
- Revise the proposal:
  - add an oracle note;
  - mention the small-model framing and the SLM paper;
  - add the code versions;
  - update the help list.
- Draft a short **Reply all** to Prof. Liu covering:
  - the oracle answer and the no-oracle numbers;
  - the 3B model with latency and memory;
  - the scorer cross-check;
  - the code versions;
  - the hosting suggestion, with a link once agreed.

---

## 9. Mac setup

Differences from Windows, all handled below:
- The Python interpreter is at `.venv/bin/python`, not `.venv/Scripts/python`.
- `requirements.lock.txt` contains a Windows-only editable `-e c:\…` line, which must be filtered out.
- `scripts/run_batch.sh` hard-codes the Windows path, so call `fineval.run` directly instead.

```bash
git clone https://github.com/Quantum-Coded/xbrl-leaderboard.git fin-eval-v1
```

```bash
cd fin-eval-v1 && git checkout -b stavan/next
```

```bash
python3 -m venv .venv
```

```bash
grep -v '^-e ' requirements.lock.txt > /tmp/req.txt && .venv/bin/python -m pip install -r /tmp/req.txt
```

```bash
.venv/bin/python -m pip install -e .
```

```bash
.venv/bin/python -I -m fineval.fetch
```

```bash
.venv/bin/python -I -m fineval.build
```

```bash
.venv/bin/python -I -m pytest -q
```

```bash
PYTHONUTF8=1 .venv/bin/python scripts/build_demo.py && git diff --stat demo/
```

```bash
cd demo && python3 -m http.server 8765
```

Open http://localhost:8765. To check the numbers, save the page text (the browser's `innerText` of the
body) to `results/audit/demo_page_text.txt`, then run:

```bash
PYTHONUTF8=1 .venv/bin/python scripts/verify_demo_page.py results/audit/demo_page_text.txt
```

Ollama: install it from https://ollama.com/download. Apple Silicon uses Metal automatically.

```bash
ollama pull qwen2.5:3b
```

```bash
ollama pull qwen2.5:7b
```

```bash
ollama pull llama3.1:8b
```

```bash
ollama list
```

In the output of `ollama list`, compare the IDs with the digests in Section 3.

A Mac run and its score:

```bash
.venv/bin/python -I -m fineval.run --model ollama:qwen2.5:3b --task concept_tagging --track tools --seed 0
```

```bash
.venv/bin/python -I -m fineval.score --run qwen2.5-3b__concept_tagging__tools__s0
```

`fineval.run` writes into `results/generations/` under the **same name** as Dev's committed run, and it
is **resumable**: if Dev's file is there, it skips every item and runs nothing. So first move Dev's
`.jsonl` and `.meta.json` for that run out of `results/generations/` (or delete them; git keeps a
copy). After the run, move your outputs and scores into `results/mac/<chip>/`, then restore Dev's
files with `git checkout -- results/generations results/scores`.
