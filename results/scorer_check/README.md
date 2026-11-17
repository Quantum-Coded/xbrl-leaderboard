# FinCL scorer check: our scorer vs FinTagging's official evaluation

- **Command:** `python -I scripts/scorer_check_fincl.py`. It writes `fincl.json`, which has per-run
  counts and every item where the two scorers disagree.
- **Official code:** `The-FinAI/FinTagging@ff426bc4c914c3cc6d967a696fbc041ed157c459`, file
  `evaluate_NEN.ipynb` (MIT). The script reproduces its parsing logic verbatim.
- **Data:** the saved outputs in `results/generations/` on the 484 scored FinCL items.
- **FinAI Evals Suite:** we searched for its code on 16 Nov 2026 and found no FinCL scorer in any
  public group repository (see the last section). FinTagging's own code stays the reference.

## Result

| Run | Ours (correct / 484) | Official (correct / 484) | Items that differ |
|---|---|---|---|
| Qwen2.5-1.5B, no tools | 8 | 8 | 0 |
| Qwen2.5-1.5B, search | 39 | 39 | 0 |
| Qwen2.5-1.5B, search + numeric | 44 | 44 | 0 |
| Qwen2.5-1.5B, search + oracle type | 47 | 47 | 0 |
| Gemma-2-2B, no tools | 3 | 3 | 0 |
| Gemma-2-2B, search | 43 | 43 | 0 |
| Gemma-2-2B, search + numeric | 39 | 39 | 0 |
| Gemma-2-2B, search + oracle type | 43 | 43 | 0 |
| Qwen2.5-3B, no tools | 5 | 5 | 0 |
| Qwen2.5-3B, search | 50 | 50 | 0 |
| Qwen2.5-3B, search + numeric | 57 | 57 | 0 |
| Qwen2.5-3B, search + oracle type | 59 | 59 | 0 |
| Llama-3.2-3B, no tools | 3 | 3 | 0 |
| Llama-3.2-3B, search | 44 | 44 | 0 |
| Llama-3.2-3B, search + numeric | 52 | 52 | 0 |
| Llama-3.2-3B, search + oracle type | 56 | 56 | 0 |
| Qwen2.5-7B, no tools | 6 | 6 | 0 |
| Qwen2.5-7B, search | 61 | 61 | 0 |
| Qwen2.5-7B, search + numeric | 71 | 71 | 0 |
| Qwen2.5-7B, search + oracle type | 75 | 75 | 0 |
| Mistral-7B, no tools | 0 | 0 | 0 |
| Mistral-7B, search | 46 | 46 | 0 |
| Mistral-7B, search + numeric | 44 | 44 | 0 |
| Mistral-7B, search + oracle type | 55 | 55 | 0 |
| Llama-3.1-8B, no tools | 8 | 8 | 0 |
| Llama-3.1-8B, search | **58** | **32** | 30 |
| Llama-3.1-8B, search + numeric | **65** | **39** | 32 |
| Llama-3.1-8B, search + oracle type | **75** | **39** | 40 |

All 28 runs (7 models × 4 conditions) agree item for item except Llama-3.1-8B's three tag-search runs.

## Why Llama-3.1-8B differs (Llama-3.2-3B does not)

- The official parser looks for `{"result"` with **no whitespace** after the brace.
- Llama-3.1-8B writes pretty-printed JSON instead: `{\n  "result": "..."}` (467 of its 581 tool-track
  outputs start with `{\n`).
- So the official code fails to parse 460 of the 484 answers. For each failure it falls back to the
  **first BM25 candidate**.
- Net effect on Llama's score:

  | Effect | Items |
  |---|---|
  | Correct model answers that the official code discards | 38 |
  | Wrong model answers where the first candidate happened to be right | 2 |
  | Net difference (75 − 39) | 36 |

## What this means

- For every model whose JSON is compact, the two scorers agree exactly.
- For Llama, the official score mostly measures the parser and the first-candidate fallback, not the
  model's answers.
- The FinTagging paper reports 9.1% for Llama-3.1-8B. That is close to the official-style 8.1% (39/484)
  here, so the paper's number may also be affected by this parser behaviour. This is **TO VERIFY**: we
  ran their code on our subset, not their full set.
- **Proposal:** report both numbers. Keep ours as the primary metric, because it accepts any valid JSON.
  Show "official FinTagging scorer" as a second column, with this note.

## Search for the FinAI Evals Suite code (16 Nov 2026)

Prof. Liu's guide links "FinAI Evals Suite" to arXiv 2602.19073 (*Evaluation and Benchmarking Suite for
Financial Large Language Models and Agents*). The paper does not use that name and gives no code
repository; it links the leaderboard Space and `finllm-leaderboard.readthedocs.io`. We checked every
public repository that could hold the suite's code, at the commits below, by searching all text files
for `fintagging`, `fincl`, `finni` and `xbrl`.

| Repository @ commit | What it is | FinTagging / FinCL scorer |
|---|---|---|
| `Open-Finance-Lab/FinLLM-Leaderboard` @ `0818040` | Source of the readthedocs site the paper links. Evaluation runs through PIXIU `flare_*` tasks. | None. Its only XBRL tagging task is FNXL (`flare_fnxl`), a different dataset. |
| `The-FinAI/FinBen` @ `74ea6b8` | `lm-eval` task files. The public repo holds only the Chinese and Greek task folders. | None |
| `finos-labs/Open-Financial-LLMs-Leaderboard` @ `0ebda4e` | Leaderboard front end and back end; it displays results and does not score. | None |
| `finos-labs/ai-evals-framework` @ `1be19cf` | Taxonomy and documents; no evaluation code. | None |
| `Open-Finance-Lab/XBRL_Tasks` @ `f8626e4` | XBRL filing samples and task data. | None |

- **Result:** no public group repository has a FinCL scorer other than FinTagging's own
  `evaluate_NEN.ipynb`, which the check above already uses.
- **Limits:** this covers public repositories only, as of the commits above. FinBen's README points to
  a `finlm_eval/` folder that is empty in the public repo, so a private or unreleased FinTagging task
  may exist. The FinTagging paper says its models were run with LM Evaluation Harness.
- **Question for Prof. Liu:** is there a FinTagging task file for `lm-eval` (FinBen) that we should use
  instead of `evaluate_NEN.ipynb`?
