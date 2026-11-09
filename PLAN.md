# Financial reporting evaluation (XBRL / SEC filings / accounting): v1 plan

*Prepared 2026-10-29 by Dev Gaglani and Stavan Desai, in response to Prof. Xiao-Yang Liu's request:
"review these resources and propose a manageable first version, covering task categories, datasets,
evaluation methods, and webpage structure … account for overlapping questions and distinguish
published scores from results reproduced under a common setup."*

---

## 1. What the project is, in one paragraph

One public, verifiable scoreboard for how well LLMs and LLM agents handle **financial reporting**:
XBRL, SEC filings and accounting rules. Instead of writing new questions, it combines five existing
benchmarks, runs every model **the same way** with **published scoring code**, removes questions that
appear in more than one source, and shows clearly which numbers were **re-run by us** and which are
**copied from papers**. It works with FINOS (Linux Foundation); the website is modelled on
Conduct Benchmark, and the research output is technical report → arXiv → conference.

## 2. Why our COLING work is the foundation

| What we did on COLING | How it carries over |
|---|---|
| Rebuilt the missing scorer and calibrated it against published numbers | Every task here needs one documented, versioned scorer |
| Found 95 test questions leaking from validation, plus duplicates | Cross-dataset deduplication is now the central data problem (see §4) |
| Kept "paper" and "ours" rows apart in one leaderboard | Exactly his second requirement |
| Validated the LLM judge against human labels (κ, TPR/TNR) | Every LLM-judged task gets the same audit |
| Showed tools (lookups, calculator) lift small models more than fine-tuning | A separate "tool-assisted / agent" track |
| Harness, run files, bootstrap CIs, table generation (`regbench/`) | Reused as the evaluation engine |

## 3. Resource review

| Resource | What it tests | Size (public) | Format / scoring | Licence | Notes |
|---|---|---|---|---|---|
| **XBRL-Agent** (Han et al., ICAIF 2024) | XBRL terminology, financial formula calculation, filing QA; agent with retriever + calculator | 6,490 terms; 50 formulas × 20 = 1,000 math Qs; 149 FinanceBench Qs | xlsx; FActScore for text, accuracy for math | MIT | Repo "work in progress"; last update 2024 |
| **Regulations Challenge** (Wang et al., 2025) | 9 tasks; XBRL part = terms, domain/numeric QA, math, tag query | 1,825 public test (8 tasks) | CSV; mixed metrics, scorer unpublished | CDLA-Permissive-2.0 | **Already reproduced by us** |
| **FinTagging** (Wang et al., 2025) | FinNI: find numeric facts in filings; FinCL: link each to a US-GAAP concept (>10k) | Eval + train sets on HF (TheFinAI); size to confirm from paper | JSON/BIO; P/R/F1, accuracy; needs Elasticsearch/BM25 retrieval | CC BY 4.0 (paper), MIT code | Best GPT-4o FinCL accuracy only 0.17 |
| **FinAuditing** (Wang et al., SIGIR 2026 resource) | FinSM: find erroneous concepts; FinRE: classify relation errors; FinMR: recompute values | 1,102 instances (330 / 440 / 332), **~34k tokens each** | HF; HR@k / macro-F1 / accuracy + LLM judge for FinMR | CC BY 4.0 | Ground truth from official XBRL US DQC errors, 218 filings, 2020–24; official SecureFinAI 2026 contest benchmark |
| **FinanceBench** (Islam et al., 2023) | Open-book QA over 10-K/10-Q PDFs with evidence | **150 open** (10,231 total, closed) | JSONL + PDFs; human-graded correctness | **CC BY-NC 4.0** | Full set needs Patronus permission; NC limits redistribution |
| Open Financial LLM Leaderboard (FINOS) | Broad finance tasks (IE, QA, risk, forecasting…) | — | HF Space (Gradio), results in TheFinAI/results | Apache-2.0 | Possible host / sister site |
| EMIR-specific RAG (FINOS) | EMIR/ESMA regulatory QA with RAG | ~116 abbr., 101 links, … | CSV | Apache-2.0 | Regulatory, not XBRL: out of v1 scope |
| Conduct Benchmark / FinCon Bench | Website model: leaderboard, compare, categories, methodology, dataset, caveats | — | — | CC BY 4.0 / Apache-2.0 | Copy: judge validation chart, CIs, provenance, "read before you quote" caveats |

## 4. Overlap: measured, not assumed (`overlap_check.py`)

| Set | Contained in | Overlap |
|---|---|---|
| COLING XBRL terminology (445, test+val) | XBRL-Agent terminology (6,490) | **445 / 445 (100%)** |
| COLING XBRL domain & numeric (99) | FinanceBench open (150) | **99 / 99 (100%)** |
| XBRL-Agent "financebench" (149) | FinanceBench open (150) | **149 / 149 (100%)** |
| COLING financial math (90 test) | XBRL-Agent formula Qs (1,000) | **90 / 90 (100%)** |
| COLING abbreviations (444) | FINOS EMIR-RAG abbreviations (116) | 103 shared |
| COLING law links (161) | FINOS ESMA links (101) | 71 shared |
| FinTagging ↔ FinAuditing ↔ COLING tag query | same SEC XBRL filings / US-GAAP 2024? | **to check** (filing-level: company + fiscal year) |

**Consequences:**
1. The XBRL half of the Regulations Challenge is a *subset* of XBRL-Agent and FinanceBench, so it
   must not be counted as a separate source.
2. Every item gets a **canonical ID**: source dataset, original ID, plus a normalized-text hash and
   filing key. Duplicates are merged and their provenance kept.
3. The website shows overlap counts per source, so readers can see what's really independent.

## 5. Proposed v1 scope (manageable)

**Principle:** 4 task categories, deterministic scoring wherever possible, and inputs that fit
local-model context limits. Long-context auditing becomes v1.5, once compute is confirmed.

| # | Category | Data (after dedup) | Primary metric | Why in v1 |
|---|---|---|---|---|
| 1 | **XBRL concepts & tagging** | FinTagging FinCL (subset) + COLING tag query (90) | accuracy on concept ID (exact element match) | Deterministic; models are very weak (≤0.17); tools should help most |
| 2 | **Fact extraction from filings** | FinTagging FinNI (subset) | entity-level P/R/F1 | Deterministic; core of XBRL tagging |
| 3 | **Financial calculation** | XBRL-Agent formulas (1,000 → dedup) | numeric match with **published unit rules** | Deterministic; our COLING work showed the unit pitfalls |
| 4 | **Filing QA with evidence** | FinanceBench open 150 (covers COLING 99) | correctness via validated LLM judge + evidence check | Realistic; tests retrieval over real 10-Ks |
| v1.5 | **Consistency auditing** | FinAuditing FinSM/FinRE/FinMR (1,102) | HR@k, macro-F1, accuracy | ~34k-token inputs need long-context GPUs or API |
| opt. | **XBRL terminology** | XBRL-Agent terms (sample, e.g. 500) | reference-grounded judge (strict & lenient, audited) | Cheap; judge-dependent, so labelled as such |

**Two evaluation tracks:**
- **Closed-book:** the model alone, with official prompts.
- **Tool-assisted (agent):** the same models with lookup tools (US-GAAP taxonomy search, calculator,
  filing retrieval), as in XBRL-Agent and our RegSys. Reporting both separates "knows it" from
  "can find it".

**Models (v1):**
- **Run by us:** open models we can run (Llama-3.1-8B, Qwen2.5-7B, …) under the common setup.
- **From papers:** GPT-4o, DeepSeek-V3 and others, shown as "published" until re-run with API
  access.

**Splits:** test only for scoring. Validation, or the released training sets, only for prompts and
few-shot examples, with an automatic leakage check (as in COLING).

## 6. Evaluation methodology (the research contribution)

1. **Published, versioned scorer for every task.** No hidden matching rules. Report strict and
   lenient variants where answers are free text.
2. **Deterministic checks first; LLM judges only for free text.** Each judge is validated against
   human labels (agreement, κ, TPR/TNR) before its numbers go on the site.
3. **Published vs reproduced:** every cell is tagged *paper* or *ours*, with the gap shown. Our
   reproduced rows include model version, precision, prompt and seed.
4. **Uncertainty:** bootstrap 95% CIs on every score and paired tests for comparisons. Differences
   inside the noise are not ranked.
5. **Data quality report:** overlap, duplicates, broken labels, unit conventions, licence per item.
6. **Stability:** reruns at a second seed; scoring-rule sensitivity shown, since it was the dominant
   instability in COLING.

## 7. Webpage structure (Conduct-Benchmark style)

| Page | Content |
|---|---|
| **Leaderboard** | Overall + per category; toggles for closed-book vs tool-assisted and published vs reproduced; CIs; "within noise" groups |
| **Compare** | Two models side by side, per task, with example outputs |
| **Tasks** | One page per category: definition, sources, example items, metric, common failure modes |
| **Methodology** | Scorers, judge validation charts, dedup procedure, uncertainty, caveats ("read this before quoting a number") |
| **Datasets** | Sources, licences, sizes before/after dedup, overlap matrix, provenance |
| **Reproduce** | Harness code, exact commands, result files; how to submit a model |

**Tech:** a static site (e.g. Next.js or a simple GitHub Pages site) that reads result JSON produced by
the harness. Optionally linked from or mirrored into the FINOS Open Financial LLM Leaderboard
(HF Space).

## 8. Step-by-step work plan

| Week | Step | Output |
|---|---|---|
| 0 (now) | Send short reply + this proposal | Agreement on scope |
| 1 | **Data inventory:** download all public sets; confirm sizes, fields, licences; read the FinTagging and FinAuditing papers fully | `datasets.md` table |
| 1–2 | **Dedup:** canonical IDs, text-hash and filing-key matching across all sources; overlap matrix | `overlap.json`, matrix figure |
| 2 | **Unified schema:** one JSONL format (id, source, category, input, gold, metric, licence, provenance) | `data/v1/*.jsonl` |
| 2–3 | **Scorers:** port the published metrics; add unit rules and strict/lenient variants; unit tests | `scorers/` |
| 3 | **Reproduce published numbers** on small subsets with the same open models the papers report (e.g. Llama-3.1-8B on FinTagging) | published-vs-ours table |
| 3–4 | **Closed-book runs** for all v1 categories | results JSON |
| 4–5 | **Tool-assisted track:** taxonomy search, calculator, filing retrieval | results JSON + ablation |
| 5 | **Judge validation** for FinanceBench QA (human sample, as in COLING) | κ, TPR/TNR |
| 5–6 | **Website v1** + **technical report** | site + report PDF |
| later | v1.5 FinAuditing (long context), API models, arXiv preprint, venue (e.g. SIGIR resource track, NeurIPS Datasets & Benchmarks, ACL/EMNLP) | — |

## 9. Feasibility and what we need

**Feasible now on our laptop (6 GB GPU):**
- categories 1–3, with FinTagging FinCL possibly on a subset;
- FinanceBench via retrieval chunks;
- open 7–8B models.

**Needs support:**
1. **Compute:** FinAuditing averages ~34k tokens per item, beyond a 6 GB laptop. We need a
   24–80 GB GPU or API credits to evaluate GPT-4o/Claude-class models ourselves.
2. **Data access:** the full FinanceBench (10k Qs) needs Patronus AI permission. The open 150 is
   CC BY-NC, so it can't be redistributed commercially.
3. **Coordination:** FinTagging and FinAuditing come from the same group (Yan Wang, Keyi Wang et al.).
   Their scorers, filing lists and any hidden test sets would avoid duplicate effort.
4. **Hosting/branding:** under FINOS labs, a GitHub Pages site, or the existing HF Space?

**Risks:**
- Licence limits (FinanceBench NC).
- Long-context cost.
- Judge reliability on free-text tasks; mitigated by human audits.
- Overlapping filings creating hidden leakage; mitigated by filing-level dedup.

## 10. Open questions for Prof. Liu

1. Is the 4-category v1 (+ FinAuditing in v1.5) the right first scope?
2. Can we get GPU or API access for long-context and closed models?
3. Should we coordinate directly with the FinTagging and FinAuditing authors?
4. Where should the site live (FINOS labs, the OFLL HF Space, or standalone)?
5. Is there a target timeline or venue for the technical report?
