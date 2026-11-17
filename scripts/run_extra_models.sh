#!/usr/bin/env bash
# Extra small open-weight models on FinCL (accuracy under every condition + latency/memory profiles).
# Run after scripts/run_next_stage.sh, never at the same time (one model on the GPU at a time).
#   Windows:  bash scripts/run_extra_models.sh
#   Mac:      FINEVAL_RESULTS=results/mac/<chip> bash scripts/run_extra_models.sh
#   Profiles only (skip the full accuracy runs, e.g. on a slow machine): PROFILE_ONLY=1 bash scripts/run_extra_models.sh
cd "$(dirname "$0")/.."
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=.venv/Scripts/python; fi
export PYTHONUTF8=1
MODELS=${MODELS:-"ollama:qwen2.5:1.5b ollama:gemma2:2b ollama:llama3.2:3b ollama:mistral:7b"}
safe() { echo "${1#ollama:}" | tr ':/' '-_'; }
[ -n "$PROFILE_ONLY" ] || for m in $MODELS; do for tr in closed tools tools_noorac tools_numeric; do
  $PY -I -m fineval.run --model "$m" --task concept_tagging --track $tr --seed 0 &&
  $PY -I -m fineval.score --run "$(safe "$m")__concept_tagging__${tr}__s0" > /dev/null || echo "FAILED $m concept_tagging $tr"
done; done
for m in $MODELS; do for tr in closed tools tools_noorac; do
  $PY -I scripts/profile_runs.py --model "$m" --track $tr --n 100 > /dev/null || echo "FAILED profile $m $tr"
done; done
$PY -I scripts/scorer_check_fincl.py
echo EXTRA MODELS DONE
