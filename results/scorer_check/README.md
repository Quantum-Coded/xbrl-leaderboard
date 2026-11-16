# FinCL scorer check: our scorer vs FinTagging's official evaluation

- **Command:** `python -I scripts/scorer_check_fincl.py`. It writes `fincl.json`, which has per-run
  counts and every item where the two scorers disagree.
- **Official code:** `The-FinAI/FinTagging@ff426bc4c914c3cc6d967a696fbc041ed157c459`, file
  `evaluate_NEN.ipynb` (MIT). The script reproduces its parsing logic verbatim.
- **Data:** the saved outputs in `results/generations/` on the 484 scored FinCL items.
- **Not yet verified:** whether the group's *FinAI Evals Suite* has its own FinCL scorer. We have not
  found it yet.

## Result

| Run | Ours (correct / 484) | Official (correct / 484) | Items that differ |
|---|---|---|---|
| Qwen2.5-7B, tag search | 75 | 75 | 0 |
| Qwen2.5-3B, tag search | 59 | 59 | 0 |
| Mistral-7B, tag search | 55 | 55 | 0 |
| Llama-3.1-8B, tag search | **75** | **39** | 40 |
| All four models, no tools | same | same | 0 |

## Why Llama differs

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
