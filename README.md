# XBRL Leaderboard

**Question:** what can small AI models do on financial-reporting tasks when they run on an ordinary
laptop, and what can't they do? We measure where they work, where they fail, and what they cost in
time and memory.

## Why this matters

- US public companies file their accounts with the SEC in **XBRL**: every number in a filing is
  tagged with a standard label, called a **US-GAAP concept**.
- There are **17,388** such labels, so picking the right one is hard even for experts.
- Banks and regulators prefer AI they can **run in-house** (privacy, cost). That means small,
  open-weight models (under about 10B parameters), not large cloud models.
- Nobody has clearly measured how well these small local models handle XBRL. This project does.

## What we do, step by step

1. **Take a public test set.** We use FinTagging's public subset: 484 numbers from real filings,
   each with its correct label. Duplicates and conflicting items are removed, and every removed item
   is listed.
2. **Ask each model** to pick the right label for each number. We test 4 ways:
   - **No tools:** the model answers from memory.
   - **Tag search:** a search engine first finds 100 likely labels, and the model picks one.
   - **Tag search over numeric labels only:** the same, limited to a fixed list of numeric label types.
   - **Tag search with the item's type** (an *oracle* hint that real systems don't have). This shows
     the best case and is labelled clearly.
3. **Score the answers** by exact match with the correct label, with 95% confidence intervals. We
   also check our scorer against the original authors' scoring code.
4. **Measure the cost** of each answer: time per item, and peak memory, on two laptops kept apart
   (Windows with an NVIDIA GPU, and an Apple M4 Mac).
5. **Find why answers fail:**
   - the search did not find the right label (a *retrieval* failure), or
   - the model saw it but picked another (a *selection* failure).
6. **A second task, calculation:** each model computes 1,000 financial-formula questions, once from
   memory and once with a formula lookup and a calculator.
7. **Publish everything:** the results page, the saved model answers, the code, and the exact
   versions, so anyone can re-check every number.

## Models

All are open-weight, run locally through [Ollama](https://ollama.com), 4-bit, with the same settings
on every machine.

- Qwen2.5 (1.5B, 3B, 7B)
- Llama (3.2-3B, 3.1-8B)
- Gemma-2-2B
- Mistral-7B

## Where to look

| What | Where |
|---|---|
| Results page | https://quantum-coded.github.io/xbrl-leaderboard/ (or open [`demo/index.html`](demo/index.html) locally, see below) |
| Project context and current state | [`docs/CONTEXT.md`](docs/CONTEXT.md) |
| Full method and every command | [`docs/REPRODUCE.md`](docs/REPRODUCE.md) |
| Our scorer vs the official one | [`results/scorer_check/README.md`](results/scorer_check/README.md) |
| Mac results | [`results/mac/m4/README.md`](results/mac/m4/README.md) |
| Code, data and model versions | [`docs/VERSIONS.md`](docs/VERSIONS.md) |
| Hosting plan, and how to cite | [`docs/HOSTING.md`](docs/HOSTING.md), [`CITATION.cff`](CITATION.cff) |

## Try it in 3 commands

The saved model answers are in the repo, so **no GPU is needed**. On Windows, use
`.venv/Scripts/python` instead of `.venv/bin/python`.

```bash
python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.lock.txt && .venv/bin/python -m pip install -e . && .venv/bin/python -I -m fineval.fetch && .venv/bin/python -I -m fineval.build
```

```bash
PYTHONUTF8=1 .venv/bin/python scripts/build_demo.py
```

```bash
cd demo && python3 -m http.server 8765
```

Then open http://localhost:8765.

## Built on

- [FinTagging](https://github.com/The-FinAI/FinTagging) (the task and the data)
- [XBRL-Agent](https://github.com/KirkHan0920/XBRL-Agent) (the calculation task)
- *Small Language Models are the Future of Agentic AI* ([arXiv 2506.02153](https://arxiv.org/abs/2506.02153)) (the motivation)

The work is supervised by Prof. Xiao-Yang Liu. It is by Dev Gaglani and Stavan Desai.

**Licence.** The code is under the [MIT licence](LICENSE). Data keeps its sources' licences.
