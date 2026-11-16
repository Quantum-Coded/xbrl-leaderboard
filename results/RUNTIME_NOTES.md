Runtime note: every seed-0 run started before commit adding `runtime` to run metadata used Ollama 0.40.15
(an update to 0.40.16 was downloaded by the Ollama app but never installed; the server was restarted
with `ollama serve` on 2026-11-11 after the app process was killed, still 0.40.15).

## Pause on 12 Nov 2026, 08:30 IST (GPU handed to wsp-r1)
Seed-0 generation stopped with `llama3.1-8b__financial_calc__closed__s0` at 843/1000. Not started:
llama calc tools, qwen2.5-7b calc closed/tools, mistral-7b calc closed/tools. Every other seed-0 run is
complete. The failed attempts after Ollama stopped wrote no generation files. To resume:
`ollama serve`, then `bash scripts/run_batch.sh` (finished runs are skipped).
