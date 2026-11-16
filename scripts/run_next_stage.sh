#!/usr/bin/env bash
# Next-stage runs (handoff Section 8): FinCL under every tag-search condition, profiling, calculation.
# Resumable: finished items and finished runs are skipped. Works on Windows (Git Bash) and macOS.
#   Windows:  bash scripts/run_next_stage.sh
#   Mac:      FINEVAL_RESULTS=results/mac/<chip> bash scripts/run_next_stage.sh
# Plug in first and close other heavy apps; profile_runs.py refuses to run on battery.
cd "$(dirname "$0")/.."
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=.venv/Scripts/python; fi
export PYTHONUTF8=1
MODELS=${MODELS:-"ollama:qwen2.5:3b ollama:qwen2.5:7b ollama:llama3.1:8b"}
safe() { echo "${1#ollama:}" | tr ':/' '-_'; }

# 1. accuracy on FinCL: closed, oracle tag search, no-oracle tag search, numeric-types tag search
for m in $MODELS; do for tr in closed tools tools_noorac tools_numeric; do
  $PY -I -m fineval.run --model "$m" --task concept_tagging --track $tr --seed 0 &&
  $PY -I -m fineval.score --run "$(safe "$m")__concept_tagging__${tr}__s0" || echo "FAILED $m concept_tagging $tr"
done; done

# 2. latency and peak memory on the same 100 FinCL items (one model at a time, server emptied first)
for m in $MODELS; do for tr in closed tools tools_noorac; do
  $PY -I scripts/profile_runs.py --model "$m" --track $tr --n 100 || echo "FAILED profile $m $tr"
done; done

# 3. the next task: financial calculation (XBRL-Agent formulas, 1000 items)
for m in $MODELS; do for tr in closed tools; do
  $PY -I -m fineval.run --model "$m" --task financial_calc --track $tr --seed 0 &&
  $PY -I -m fineval.score --run "$(safe "$m")__financial_calc__${tr}__s0" || echo "FAILED $m financial_calc $tr"
done; done

# 4. scorer cross-check against FinTagging's official evaluation
$PY -I scripts/scorer_check_fincl.py
echo NEXT STAGE DONE
