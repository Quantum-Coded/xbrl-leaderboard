#!/usr/bin/env bash
# Financial calculation (XBRL-Agent formulas, 1,000 items) for the extra small models, no tools and formula lookup.
# Run after scripts/run_extra_models.sh, never at the same time (one model on the GPU at a time).
#   Windows:  bash scripts/run_extra_calc.sh
#   Mac:      FINEVAL_RESULTS=results/mac/<chip> bash scripts/run_extra_calc.sh
cd "$(dirname "$0")/.."
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=.venv/Scripts/python; fi
export PYTHONUTF8=1
MODELS=${MODELS:-"ollama:qwen2.5:1.5b ollama:gemma2:2b ollama:llama3.2:3b ollama:mistral:7b"}
safe() { echo "${1#ollama:}" | tr ':/' '-_'; }
for m in $MODELS; do for tr in closed tools; do
  $PY -I -m fineval.run --model "$m" --task financial_calc --track $tr --seed 0 &&
  $PY -I -m fineval.score --run "$(safe "$m")__financial_calc__${tr}__s0" > /dev/null || echo "FAILED $m financial_calc $tr"
done; done
echo "EXTRA CALC DONE"
