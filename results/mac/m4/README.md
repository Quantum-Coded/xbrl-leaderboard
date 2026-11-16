# Mac runs (Apple M4, 16 GB)

All files here come from the Mac and are kept apart from the Windows runs in `results/generations/` and
`results/scores/`. Never mix latency or memory from the two machines.

- **Setup:** Ollama 0.40.16, upgraded from 0.34.4 on 16 Nov 2026. Model digests are the same as on
  Windows. Produced with `FINEVAL_RESULTS=results/mac/m4`.
- **Comparison with Windows:** `python -I scripts/compare_machines.py results/mac/m4` writes
  `compare_windows.json`. Every number below is in that file or in `scores/`.

## Status on 16 Nov 2026

| Run (qwen2.5:3b, FinCL, 484 items) | Mac | Windows | Items scored differently |
|---|---|---|---|
| No tools | 5 correct (1.0%) | 5 correct (1.0%) | 0 |
| Tag search, oracle type | not run yet | 59 correct (12.2%) | |
| Tag search, no type | not run yet | not run yet | |

- **No tools:** the same 5 items are correct on both machines. All 484 prompts are identical. 393 of the
  484 raw outputs are identical, and 394 parsed answers; the rest differ only among wrong answers.
- **One difference outside FinCL:** on the 90 tag-query items of the same run, the Mac gets 9 correct and
  Windows 8. These items are not on the page.
- **Why the other runs are missing:** the Mac was on battery and the run loop stopped at 4%. The
  profiler has not been run, because it needs mains power. Qwen2.5-7B and Llama-3.1-8B have not been run.
