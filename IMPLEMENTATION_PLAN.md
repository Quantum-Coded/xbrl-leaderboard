# FinEval v1: implementation plan

*Dev Gaglani and Stavan Desai. Companion to [`PLAN.md`](PLAN.md), which covers scope and rationale. This
file says exactly what gets built, in what order, and how each step is tested. Nothing is
implemented until the go-ahead.*

---

## 0. Ground rules (apply to every phase)

1. **No number without a file behind it.** Every dataset size, overlap count, score and published
   figure on the site or in the report comes from a file in the repo: a result JSON, a manifest,
   or `reference/published.json`. That last file holds a citation, page and table for every entry.
   A test fails the build if the site or report shows a number not traceable to one of these.
2. **Every source is pinned.** Each download records URL, git commit or HF revision, retrieval date,
   SHA-256 and licence in `data/raw/MANIFEST.json`. Loaders refuse files whose hash doesn't match.
3. **Unverified means labelled.** Anything not yet checked against the source (e.g. FinTagging's
   size) stays marked `TO VERIFY` in docs and never appears as a fact.
4. **Test data is never used for tuning.** Prompts, few-shot examples and training draw only on
   train/validation splits. Every duplicate cluster is checked so no copy of a test item leaks in.
5. **Deterministic runs.** Greedy decoding, fixed seed, pinned model files (hash recorded),
   resumable JSONL outputs. A second seed is run on a subset to measure stability.
6. **Downloads are untrusted data.** Each source goes in its own directory, Python reading it runs
   with `-I`, and no pickle or `trust_remote_code` weights are used without approval.
7. **Git:** commits as Quantum-Coded only, with no AI attribution, and no push until you say so.

## 1. Repository layout

New folder `fin-eval-v1/` becomes a git repo, with a private GitHub repo created only when you
approve the push.

```
fin-eval-v1/
  fineval/                 Python package (reuses regbench code where it fits)
    sources/               one loader per dataset -> unified records
    schema.py              record dataclass + JSON schema validation
    normalize.py           text / number / unit / concept-ID normalisation
    dedup.py               exact + near-duplicate clustering, filing keys, conflict report
    splits.py              group-aware test/dev/train assignment
    prompts/               closed-book and tool-assisted templates per task
    tools/                 taxonomy search (BM25), calculator (safe_eval), filing retrieval
    llm.py                 Ollama / llama.cpp backends (from regbench)
    run.py                 resumable generation
    scorers/               one versioned scorer per task
    judge/                 LLM judge + human-label audit (from regbench judge_audit)
    stats.py               bootstrap CIs, paired tests, "within noise" grouping
    train/                 optional LoRA fine-tune (Phase 7)
    export.py              results -> site JSON
  data/raw/<source>/       pinned downloads (gitignored if licence forbids redistribution)
  data/raw/MANIFEST.json
  data/v1/                 unified JSONL per task + overlap.json + conflicts.csv
  reference/published.json published scores with citation, page, table
  results/                 generations, judgements, scores
  site/                    static website
  report/                  technical report (LaTeX, two-column)
  tests/                   pytest suite
```

## 2. Phases

Each phase has tasks, outputs and an **exit test**. A phase is done only when its exit test passes.

### Phase 0: Environment and feasibility (days 1–2)

- Create the repo and a Python 3.10 venv with pinned `requirements.txt` (pandas, datasets, rank_bm25,
  rapidfuzz, datasketch, bert-score, pytest, jsonschema).
- Check whether Node is installed (needed for the site). If not, ask before installing.
- Measure throughput and VRAM for the candidate models already on disk (Llama-3.1-8B, Qwen2.5-7B,
  Mistral-7B, Qwen2.5-3B) at context lengths of 2k, 4k and 8k. An 8B Q4 model plus an 8k KV cache
  is close to 6 GB, so we pick each task's context length from these measurements, not by guessing.
- Port from regbench: `llm.py`, `safe_eval`, bootstrap code and the judge-audit code, with their tests.

**Exit test:** `pytest` is green on the ported modules, and `results/feasibility.json` holds tokens/s
and peak VRAM for each model × context length.

### Phase 1: Data inventory (days 2–5)

For each source, download it, pin it, read its paper's dataset section, and write a datasheet entry:

| Source | What we pull | Things to verify from the source itself |
|---|---|---|
| FinTagging | FinNI + FinCL eval sets, train sets, US-GAAP concept list | sizes, fields, split names, taxonomy year, filing IDs, licence |
| XBRL-Agent | terminology xlsx, formula xlsx, financebench xlsx | sizes, gold-answer format, units |
| FinanceBench | `financebench_open_source.jsonl` + PDFs referenced | 150 Qs, evidence fields, doc names, CC BY-NC terms |
| Regulations Challenge | XBRL terms, domain/numeric, math, tag query (already local) | same as COLING repo |
| US-GAAP taxonomy | the year(s) FinTagging and the tag query use | version match |
| Published scores | tables from each paper | page and table number for every number |

**Output:** `data/raw/MANIFEST.json`, `docs/datasheet.md`, `reference/published.json`.

**Exit test:** a test re-hashes every raw file against the manifest. Every row in
`published.json` has a citation, page and table. Every count in `datasheet.md` is computed by a
script, not typed by hand.

### Phase 2: Unified schema (days 5–7)

One record per item:

```json
{"uid": "fintagging:fincl:test:000123", "source": "fintagging", "source_id": "...",
 "source_split": "test", "task": "concept_tagging", "input": {...}, "gold": {...},
 "metric": "exact_concept@v1", "filing_key": "CIK0000320193-FY2023-10K",
 "licence": "CC-BY-4.0", "provenance": {"file": "...", "row": 123, "sha256": "..."}}
```

- Every loader is a pure function from a raw file to records, validated against a JSON schema.
- **Gold answers are never rewritten.** Normalisation happens only inside scorers and dedup, and
  the original text is always kept.

**Exit test:** schema validation passes on 100% of records. Per-source record counts equal the
Phase 1 counts. Round-trip tests run on 20 random items per source, comparing raw row to record
by hand-checked fixtures.

### Phase 3: Duplicate handling (days 7–11)

This is the core data contribution, so it gets the most testing.

**3.1 Keys computed for every item**
- `text_norm`: NFKC, lowercase, collapse whitespace, strip punctuation, standardise numbers
  ("1,000" → "1000", "$" and "USD" unified).
- `exact_hash`: SHA-1 of `text_norm` (question + any context that defines the item).
- `filing_key`: company identifier (CIK, else a normalised company name mapped to CIK through the
  SEC ticker/CIK list), fiscal year and form type. Built from FinanceBench `doc_name`, FinTagging
  filing metadata and XBRL-Agent rows.
- `concept_key` for tagging items: a normalised US-GAAP element name.

**3.2 Clustering**
- **Exact:** items with equal `exact_hash` are joined.
- **Near-duplicate:** MinHash LSH on word 3-gram shingles finds candidates, then RapidFuzz token-set
  ratio scores them. Pairs at ≥ 0.90 are joined automatically. Pairs in 0.75–0.90 go to
  `review/near_dups.csv` for a human decision, which is stored and re-applied on every rebuild.
  Thresholds are calibrated on the known overlaps (COLING ⊂ XBRL-Agent / FinanceBench), which must
  all be recovered.
- **Union-find** over the joins gives clusters. Each cluster gets a stable `cluster_id`.

**3.3 Inside a cluster**
- **Representative:** the original source wins (FinanceBench > XBRL-Agent > Regulations Challenge),
  and the others are kept as `also_in`.
- **Gold conflicts:** if members' gold answers differ after normalisation, the cluster is written to
  `data/v1/conflicts.csv` and **not** merged silently. We keep the original source's gold, flag the
  item, and report the conflict count on the site.
- The **filing-level overlap** across FinTagging, FinAuditing and the tag queries is reported as its
  own matrix. Different questions about the same filing are not duplicates, but they matter for
  leakage.

**3.4 Outputs:** `data/v1/overlap.json` (pairwise counts, sources × sources), `clusters.jsonl`,
`conflicts.csv`, and a overlap figure for the site.

**Exit tests:**
- **Known overlaps:** 445/445 terms, 99/99 domain/numeric, 149/149 XBRL-Agent FinanceBench and
  90/90 math are recovered, matching `overlap_check.py`.
- **Synthetic tests:** case, spacing and number-format variants must cluster, and different numbers
  in otherwise identical questions must **not** cluster.
- **Reproducibility:** clustering is deterministic and independent of input order (shuffled-input
  test).
- **Hand audit:** 50 auto-joined pairs and 50 non-joined high-similarity pairs are checked by hand,
  with precision and recall written to `docs/dedup_audit.md`.

### Phase 4: Splits and leakage control (days 11–12)

- The **test set** is each source's own test split. One cluster appears once.
- **Dev/train pools** come from source train/validation splits, minus **every cluster and every
  filing** that touches test. Assignment is group-aware, so no cluster or filing crosses splits.
- **Evaluation subsets:** where a full test set is too slow on our GPU (sized from the Phase 0
  throughput numbers), we draw a fixed, stratified, seeded subset and state its size and seed. Full
  runs follow whenever compute allows.

**Exit test:** a leakage test asserts zero shared `cluster_id` and zero shared `filing_key` between
test and train/dev, and that subset IDs are identical across reruns.

### Phase 5: Scorers and reproduction of published numbers (days 12–18)

| Task | Primary metric | Variants | Source of the rule |
|---|---|---|---|
| Concept tagging (FinCL + tag query) | exact element-ID accuracy | case/namespace-insensitive lenient | FinTagging paper + COLING |
| Fact extraction (FinNI) | entity-level micro P/R/F1 | strict span vs lenient overlap | FinTagging paper |
| Financial calculation | numeric match on final value | relative tolerance; unit-agnostic sensitivity | XBRL-Agent + COLING unit lessons |
| Filing QA (FinanceBench) | correctness by validated judge | strict/lenient; numeric check where gold is a number | FinanceBench paper |

- Each scorer is versioned (`exact_concept@v1`), documented in `docs/protocol.md`, and has
  **golden tests** that pin hand-written examples to expected scores, including edge cases (units,
  negatives, percentages, empty answers, refusals).
- **Reproduction:** for each paper, we re-run at least one open model it reports, under its stated
  setup, on the same items. Each result goes into a published-vs-ours table with a bootstrap CI.
  A gap outside the CI is investigated and explained in the report, never tuned away on test data.

**Exit test:** golden tests pass, and every scorer gives identical output on rerun. The reproduction
table is generated from files, with each gap explained or marked as open.

### Phase 6: Evaluation runs (days 18–28)

- **Closed-book track:** official or paper prompts and no tools, for every model × task.
- **Tool-assisted track:** the same models with:
  - **Taxonomy search:** BM25 over US-GAAP labels and definitions, returning top-k candidates.
    FinTagging used Elasticsearch; we use BM25 in Python, which is a documented deviation.
  - **Calculator:** AST-whitelisted `safe_eval`, already in regbench.
  - **Filing retrieval:** FinanceBench PDFs are chunked and searched with BM25 (optionally a small
    embedding model), and the model must cite its evidence page.
- **Ablation:** each tool is removed in turn, on a subset.
- **Stability:** a second seed on a subset, with agreement reported.
- **Order:** runs are queued resumably, as in `pipeline.sh`. Long jobs run in the background, and
  other GPU jobs are never stopped without asking you.

**Exit test:** every planned (model, task, track) run has 100% of items generated and scored. The
stability report shows score spread within the CI, or flags it.

### Phase 7: Training (optional, days 22–30, parallel with Phase 6)

The goal is a fair answer to "does fine-tuning beat tools?" on the same benchmark.
- **Data:** FinTagging's released train split (and XBRL-Agent terms not in any test cluster), after
  the Phase 4 leakage filter.
- **Method:** QLoRA on a small open model (Qwen2.5-3B first; 7B only if it fits in 6 GB at a usable
  speed), using a fixed seed and hyper-parameters chosen on dev only.
- **Feasibility gate:** a 200-step smoke run must finish and improve dev loss. If it doesn't fit the
  laptop, the phase is reported as deferred, not forced.
- **Evaluation:** closed-book and tool-assisted, side by side with the base model, using paired
  bootstrap.

**Exit test:** the training data manifest proves zero overlap with test clusters and filings. The
results table is generated from files, whatever the outcome.

### Phase 8: Judge validation (days 26–30)

- For FinanceBench QA (the only judge-scored task in v1), we use a cross-family judge with an
  abstention rule (refusals score 0), reusing COLING's FActScore v2 lessons.
- **Human audit:** Dev and Stavan label a stratified sample (~100 items) independently, using a
  labelling guide adapted from `docs/judge_labeling_guide.md`. We report agreement between the two,
  then the judge's κ, TPR and TNR against their consensus.
- **Sensitivity:** leaderboard order is computed under strict and lenient judging.

**Exit test:** the judge's κ against consensus is reported, with the threshold decided **before**
seeing results (κ ≥ 0.6 to publish judge scores as primary; otherwise they're shown as provisional
with a warning).

### Phase 9: Website (days 26–36)

- **Stack:** a static site built with Vite + React + TypeScript, reading only `site/data/*.json`
  produced by `fineval/export.py`, and deployable to GitHub Pages. Hosting under FINOS or the HF
  Space is decided later and needs no code change.
- **Pages:**
  - **Leaderboard:** overall and per category; toggles for closed-book vs tool-assisted and
    published vs reproduced; CIs; "within noise" groups.
  - **Compare:** two models side by side per task, with example outputs.
  - **Tasks:** one page per category with definition, sources, examples, metric and failure modes.
  - **Methodology:** scorers, dedup procedure, judge-validation chart, uncertainty and caveats.
  - **Datasets:** sources, licences, sizes before and after dedup, overlap matrix and conflicts.
  - **Reproduce:** commands, harness link, result files and a submission guide.
- **Licensing:** FinanceBench items (CC BY-NC) are shown only as short examples with attribution,
  and the full text is not redistributed on the site.

**Exit tests:**
- `npm run build` succeeds with no warnings treated as errors.
- A **number-consistency test** checks that every number rendered on the site appears in
  `site/data/*.json`, and that every value there matches `results/`.
- A link checker passes.
- Pages render at mobile and desktop widths, checked in the browser pane.
- Light and dark mode both work.

### Phase 10: Technical report (days 32–42)

- A two-column LaTeX report, reusing the COLING paper setup. Every table is generated from `results/`
  by a script, as `paper_tables.py` does.
- **Sections:** motivation; sources and datasheet; dedup method and overlap findings; tasks and
  scorers; published-vs-reproduced; closed-book vs tool-assisted (+ training); judge validation;
  limitations (hardware, open models only, subsets, licences); glossary.

**Exit test:** the PDF compiles, and a script checks that every number in the `.tex` file comes from
`numbers.json`.

## 3. Testing summary

| Layer | Tests |
|---|---|
| Sources | hash pinning, count equality, schema validation, round-trip fixtures |
| Dedup | known-overlap recovery, synthetic variants, order invariance, hand audit |
| Splits | zero cluster/filing leakage, fixed subsets |
| Scorers | golden tests, edge cases, determinism |
| Runs | completeness, stability across seeds |
| Judge | human agreement, κ threshold set in advance |
| Site and report | build, number consistency, links, responsive and dark mode |

All of this runs with one command (`pytest` + `npm test`). Every phase ends green before the next
one starts.

## 4. Timeline

| Weeks | Phases |
|---|---|
| 1 | 0 environment, 1 inventory, start 2 schema |
| 2 | 2 schema, 3 dedup, 4 splits |
| 3 | 5 scorers + reproduction |
| 4 | 6 evaluation runs, start 7 training |
| 5 | 6/7 finish, 8 judge validation, start 9 website |
| 6 | 9 website, 10 technical report draft |

FinAuditing (v1.5) plugs into the same pipeline once larger GPU or API access is available.

## 5. Decisions taken, and what needs your OK

**Decided:**
- Work lives in `fin-eval-v1/`, reusing regbench code by copying it in (with tests), not by
  importing across repos.
- Python harness, Vite + React static site, GitHub Pages as the default target.
- Open-source models only, run locally.
- Test sets are used only for scoring.

**Needs your OK when we reach it:**
- Installing Node if it's missing.
- Creating the GitHub repo and pushing.
- Stopping any other GPU job.
- Any download that isn't one of the listed sources.
