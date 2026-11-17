# Mac runs (Apple M4, 16 GB)

All files here come from the Mac and are kept apart from the Windows runs in `results/generations/` and
`results/scores/`. Never mix latency or memory from the two machines.

- **Setup:** Ollama 0.40.16, upgraded from 0.34.4 on 16 Nov 2026 (Windows used 0.40.15). Model digests
  are the same as on Windows. Produced with `FINEVAL_RESULTS=results/mac/m4`. All profiles on mains power.
- **Comparison with Windows:** `python -I scripts/compare_machines.py results/mac/m4` writes
  `compare_windows.json`. Every number below is in that file, in `scores/` or in `profile/m4/`.

## Accuracy, qwen2.5:3b, FinCL (484 items)

| Condition | Mac | Windows | Items scored differently |
|---|---|---|---|
| No tools | 5 correct, 1.0% (CI 0.2 to 2.1) | 5 correct, 1.0% | 0 |
| Tag search, oracle type | 57 correct, 11.8% (CI 8.9 to 14.9) | 59 correct, 12.2% | 4 |
| Tag search, no type | 47 correct, 9.7% (CI 7.2 to 12.4) | no committed run | |

- **Inputs are the same.** All 484 prompts are identical on both machines in both compared runs, and
  the model digest is the same.
- **Outputs are not all the same.** No tools: 393 of 484 raw outputs are identical. Oracle tag search:
  392 of 484. The model does not give byte-identical text on the two machines.
- **Oracle tag search differs by 2 items.** Windows is correct and the Mac wrong on items 137, 326 and
  464; the Mac is correct and Windows wrong on item 383. The Mac result is inside the Windows 95% CI.
- **Coverage.** The correct concept is among the candidates for 171 items (35.3%) with the oracle type,
  the same as on Windows, and for 134 items (27.7%) without it. When covered, the model picks it on 56
  of 171 (32.7%) and 46 of 134 (34.3%). In each run 1 correct answer was not among the candidates.
- **One difference outside FinCL:** on the 90 tag-query items of the no-tools run, the Mac gets 9
  correct and Windows 8. These items are not on the page.

## Latency and peak memory, qwen2.5:3b (100 items per condition, mains power)

| Condition | Median latency | 90th percentile | Prompt tokens (median) | Loaded model | Peak Ollama process memory |
|---|---|---|---|---|---|
| No tools | 1.04 s | 1.48 s | 143 | 2,063 MiB | 2,363 MiB |
| Tag search, oracle type | 9.06 s | 12.17 s | 1,963 | 2,063 MiB | 6,871 MiB |
| Tag search, no type | 8.53 s | 10.85 s | 2,073 | 2,063 MiB | 6,932 MiB |

These are Mac numbers only. There is no committed Windows profile to set beside them.

## Accuracy, qwen2.5:7b, FinCL (484 items)

| Condition | Mac | Windows | Items scored differently |
|---|---|---|---|
| No tools | 7 correct, 1.4% (CI 0.4 to 2.7) | 6 correct, 1.2% | 1 |
| Tag search, oracle type | 72 correct, 14.9% (CI 11.8 to 18.2) | 75 correct, 15.5% | 3 |
| Tag search, no type | 62 correct, 12.8% (CI 9.9 to 15.9) | no committed run | |

- **Inputs are the same:** all 484 prompts and the model digest match in both compared runs.
- **Raw outputs identical:** 393 of 484 with no tools, 454 of 484 with oracle tag search.
- **No tools:** the Mac is also correct on item 354. **Oracle tag search:** Windows is correct and the
  Mac wrong on items 272, 431 and 485. The Mac result is inside the Windows 95% CI.
- **Coverage:** 171 items (35.3%) with the oracle type and 134 (27.7%) without, the same as for the 3B
  model. When covered, the model picks the concept on 72 of 171 (42.1%) and 61 of 134 (45.5%).
- Part of the no-type run was made on battery during a power cut. Accuracy does not depend on power.

## Latency and peak memory, qwen2.5:7b (100 items, mains power)

| Condition | Median latency | 90th percentile | Prompt tokens (median) | Loaded model | Peak Ollama process memory |
|---|---|---|---|---|---|
| No tools | 1.52 s | 2.35 s | 143 | 4,535 MiB | 4,965 MiB |
| Tag search, oracle type | 15.65 s | 19.52 s | 1,963 | 4,535 MiB | 3,572 MiB |
| Tag search, no type | 17.43 s | 21.70 s | 2,073 | 4,535 MiB | 5,027 MiB |

The no-tools profile was run on 16 Nov, the two tag-search profiles on 17 Nov (the first attempt was
refused on battery during a power cut). All three on mains power, same Ollama version and digest.

## Accuracy, llama3.1:8b, FinCL (484 items)

| Condition | Mac | Windows | Items scored differently |
|---|---|---|---|
| No tools | 7 correct, 1.4% (CI 0.4 to 2.7) | 8 correct, 1.7% | 3 |
| Tag search, oracle type | 71 correct, 14.7% (CI 11.6 to 18.0) | 75 correct, 15.5% | 4 |
| Tag search, no type | 57 correct, 11.8% (CI 9.1 to 14.7) | no committed run | |

- **Inputs are the same:** all 484 prompts and the model digest match in both compared runs.
- **Raw outputs identical:** 379 of 484 with no tools, 447 of 484 with oracle tag search.
- **No tools:** the Mac only is correct on item 10; Windows only on items 114 and 323. **Oracle tag
  search:** Windows is correct and the Mac wrong on items 102, 176, 272 and 433.
- **Coverage:** 171 (35.3%) with the oracle type and 134 (27.7%) without. When covered, the model picks
  the concept on 71 of 171 (41.5%) and 56 of 134 (41.8%).
- Run on 17 Nov 2026; part of the no-type run was on battery. Accuracy does not depend on power.

## Latency and peak memory, llama3.1:8b (100 items, mains power)

| Condition | Median latency | 90th percentile | Prompt tokens (median) | Loaded model | Peak Ollama process memory |
|---|---|---|---|---|---|
| No tools | 1.50 s | 1.88 s | 114 | 5,035 MiB | 5,663 MiB |
| Tag search, oracle type | 21.87 s | 28.14 s | 1,933 | 5,035 MiB | 6,022 MiB |
| Tag search, no type | 20.51 s | 27.84 s | 1,797 | 5,035 MiB | 6,610 MiB |

Run on 17 Nov 2026, all three on mains power. Llama uses a different tokenizer, so its prompt token
counts differ from Qwen's for the same prompts.

## Notes on all three models

- **Oracle tag search is lower on the Mac for every model:** 3B by 2 items, 7B by 3, 8B by 4. Each is
  inside the Windows 95% CI. All prompts and digests match, so the cause is in the model output, which
  is not byte-identical across the two machines (Ollama 0.40.16 on the M4 vs 0.40.15 on the RTX 4050).
- **Peak Ollama process memory** is the resident memory of the Ollama processes as the profiler
  samples it. It is not consistent with the loaded model size: for 7B oracle tag search it is 3,572 MiB,
  below the 4,535 MiB model. The cause is not checked. Use "Loaded model" for the model's own memory.
