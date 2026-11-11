#!/usr/bin/env bash
# Phase 5/6 generation batch, run serially (one model on the GPU at a time). Resumable.
cd "$(dirname "$0")/.."
PY=.venv/Scripts/python
MODELS="ollama:qwen2.5:3b ollama:llama3.1:8b ollama:qwen2.5:7b ollama:mistral:7b"
SEED=${SEED:-0}
for m in $MODELS; do for t in concept_tagging fact_extraction filing_qa; do
  $PY -I -m fineval.run --model $m --task $t --track closed --seed $SEED || echo "FAILED $m $t closed"; done; done
for m in $MODELS; do for t in concept_tagging filing_qa; do
  $PY -I -m fineval.run --model $m --task $t --track tools --seed $SEED || echo "FAILED $m $t tools"; done; done
for m in $MODELS; do for tr in closed tools; do
  $PY -I -m fineval.run --model $m --task financial_calc --track $tr --seed $SEED || echo "FAILED $m calc $tr"; done; done
echo BATCH DONE
