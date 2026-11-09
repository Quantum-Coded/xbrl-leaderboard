# FinEval v1 evaluation protocol

This file describes how every number in FinEval v1 is produced and checked. Counts are not repeated
here; they live in `data/v1/summary.json`, `docs/datasheet.md` and `report/numbers.tex`.

## 1. Data

1. `python -I -m fineval.fetch` downloads every source file from a pinned commit and records its
   SHA-256 in `data/raw/MANIFEST.json`. A file whose hash changes is refused. `--verify` re-checks.
2. `python -I -m fineval.build` loads, deduplicates, splits and writes `data/v1/`. The build is
   deterministic (`tests/test_build_determinism.py`).
3. `python -I -m fineval.datasheet` regenerates `docs/datasheet.md`.

Scripts that read downloaded files run with `python -I`, so nothing in a data folder can be imported.

## 2. Duplicates and conflicts

- **Joins:** two records join only if they share a FinanceBench id or their normalised text is
  identical (`fineval/normalize.py: text_key`). Clusters come from union-find.
- **Near-duplicates:** they are never joined automatically. MinHash LSH plus a character-ratio
  filter writes candidate pairs to `review/near_dups.csv`. Only cross-dataset pairs with the same
  numbers and no exact partner are listed. A reviewer fills in the `decision` column, using `join`
  to merge the pair or any other non-empty value (for example `distinct`) to keep it apart. The next
  build applies the decisions, and blank rows count as pending.
- **Representative:** each cluster keeps one representative. Source priority is FinanceBench, then
  XBRL-Agent or FinTagging, then COLING. Test is preferred over validation, and validation over
  train.
- **Cross-source gold disagreement:** the original publisher's gold is kept and the item is flagged
  `source_disagreement`. It stays in the primary score.
- **Same dataset, same input, different gold:** the item is flagged `ambiguous` and the gold becomes
  the union of answers. It is excluded from the primary score but kept in `all_items`.
- **Training items:** conflicting training items are dropped.

## 3. Splits and leakage

- **Clusters:** each cluster gets one split. If any member is test, the whole cluster is test.
- **Training items:** a training item is dropped if it conflicts, is a near-duplicate of an
  evaluation item, or contains test text. `fineval/train_data.py` re-checks this when it builds the
  SFT files.
- **Validation and few-shot:** validation items whose filing is in test are flagged
  `filing_in_test`. `fewshot_pool` excludes the item's cluster and its filing.
- **No test tuning:** no prompt, retrieval setting, threshold or hyperparameter is tuned on test
  items. Choices are made a priori, or on training data held out by source item.

## 4. Running models

```
python -I -m fineval.run --model ollama:qwen2.5:7b --task concept_tagging --track closed --seed 0
python -I -m fineval.score --run <run name>
```

- **Generations:** they are resumable, and stored in `results/generations/<run>.jsonl` with a
  `.meta.json` file. The meta file records the model digest, prompt version, decoding settings and
  context sizes.
- **Context:** it is chosen per item. An item that does not fit the context cap is marked
  `skipped_context` and scores zero, as does a truncated or missing generation.
- **Tracks:** there are two. `closed` gives the model only the item. `tools` adds deterministic
  local tools: taxonomy BM25 search, formula search with a whitelisted calculator, and filing page
  search. Retrieval ceilings come from `python -I -m fineval.retrieval_eval` and are reported
  before any model runs.
- **Seeds:** every headline result has a second seed.

## 5. Scoring and statistics

- **Metrics:** each metric is versioned as `name@vN` (`fineval/scorers.py`). If a rule changes, its
  version number changes too, and old scores are not mixed with new ones.
- **Reported blocks:** each run reports `primary`, `all_items` and `by_subset` blocks, each with a
  bootstrap 95% CI.
- **Comparisons:** models are compared with a paired bootstrap on the same items.

## 6. Judge (filing QA)

- **Cross-family judge:** the judge must come from a different model family than the judged model.
  `judge_run` refuses otherwise.
- **Blind audit:** `python -I -m fineval.judge --export-audit <run>` writes a blind CSV. Two
  annotators fill in their label columns independently.
- **Agreement:** `--audit` reports their agreement, plus the judge's κ, TPR and TNR against their
  consensus.
- **Publication threshold:** it was fixed before labelling. Judge scores are primary only if κ ≥ 0.6;
  otherwise they are shown as provisional.

## 7. Published versus reproduced

- **Source of published numbers:** they are copied verbatim into `reference/published.json`, with
  the paper version, page and table.
- **Item-set relation:** each published row states how its item set relates to ours (`same items as one subset`,
  `subset of items` or `different item set`). FinTagging's paper uses the full gated sets; we use the public
  subsets.
- **Separate rankings:** published and reproduced rows are never ranked together. The site groups
  published rows by evaluation set and lists measured rows separately with CIs.

## 8. Website and report

- **Exported data:** `python -I -m fineval.export` writes `site/public/data/*.json`. The site reads
  nothing else.
- **No typed numbers in the site:** `tests/test_site.py` checks that the page source contains no
  typed figures, that published values match the reference file, and that dataset numbers match the
  build.
- **Browser number check:** run it after each export. Start `npm --prefix site run preview`, then on
  every page collect the rendered numbers and confirm that each one is a formatted value from the
  exported JSON. The only known exceptions are a commit-hash fragment and model names.
- **Report:** `python -I -m fineval.report_tables` writes `report/numbers.tex` and
  `report/tables/*.tex`. `tests/test_report.py` checks that `report/main.tex` contains no typed
  figures. Compile with `tectonic report/main.tex`.

## 9. Training

`python -I -m fineval.train_data` builds the SFT files from the train split. QLoRA runs in
`.venv-train` (system torch, transformers and bitsandbytes, plus peft; see
`requirements-train.lock.txt`):

```
.venv-train/Scripts/python -m fineval.train_qlora --base models/base/Qwen2.5-3B-Instruct --data fincl --out models/qwen3b-fincl --smoke
```

- **Smoke gate:** the smoke run has to lower loss on held-out training items before a full run.
- **Loading weights:** weights load from safetensors only, with `trust_remote_code=False`.
