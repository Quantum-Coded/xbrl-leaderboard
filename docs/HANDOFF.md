# Handoff: Stavan's next steps (from 18 Nov 2026)

Read [`CONTEXT.md`](CONTEXT.md) first: it says what the project is, what is done and every verified
number. This file says only what is left for you and how to do it. The older, longer handoff is
[`HANDOFF_STAVAN.md`](HANDOFF_STAVAN.md); keep it for background only.

## What changed since you merged `stavan/next`

Dev finished the Windows work and also did the tasks that did not need a Mac:

- **Windows runs:**
  - all seven models under all four tagging conditions;
  - latency and memory profiles;
  - calculation for all seven models (the last three finished on 23 Nov with `scripts/safe_run.py`,
    which runs short chunks with pauses after long GPU runs restarted the laptop; see CONTEXT.md
    Section 8);
  - calculation speed and memory profiles for all seven models (`profile_runs.py --task financial_calc`);
  - the scorer check for every model.
- **Page v2** (`demo/`):
  - models × conditions;
  - a cost block per machine, Windows and Mac shown separately;
  - Mac vs Windows accuracy;
  - why models fail;
  - a Calculation tab.

  `scripts/build_demo.py` and `scripts/verify_demo_page.py` were rewritten for it, and
  `scripts/page_text.py` was added.
- **Hosting:**
  - `.github/workflows/pages.yml` publishes `demo/` to GitHub Pages on every push to `master` that
    touches `demo/`;
  - the address is `https://quantum-coded.github.io/xbrl-leaderboard/` (see CONTEXT.md for whether it
    is live).
- **Docs:**
  - the plain-language `README.md`;
  - `docs/REPRODUCE.md`, which holds the technical commands;
  - `LICENSE` (MIT, code only);
  - the revised `proposal/proposal.pdf` (the old version is in `proposal/archive/`);
  - `docs/FINOS_ISSUE_DRAFT.md`.
- **Drafts:** the Reply-all email is drafted but **not sent**. Dev keeps it outside the repo and sends
  it only after you both agree.

Your branch rules are unchanged. Work on `stavan/next`, put Mac results under `results/mac/m4/`, never
push to `master` alone, and add no AI attribution in commits.

## Step 1: sync and check (about 20 minutes)

1. Run `git checkout stavan/next`, then `git merge master` (fast-forward). Then run
   `.venv/bin/python -m pip install -e .`.
2. Run `pytest -q`. It should show 106 passed. If any `site/public/data/*.json` changes, restore it with
   `git checkout -- site/public/data`.
3. Run `PYTHONUTF8=1 .venv/bin/python -I scripts/build_demo.py`. It must finish with no assertion
   error, and `git diff --stat demo/` must be empty.
4. Check the page:

   ```bash
   cd demo && python3 -m http.server 8765
   ```

   In a second terminal:

   ```bash
   .venv/bin/python -I scripts/page_text.py http://localhost:8765/ /tmp/page.txt
   ```

   ```bash
   PYTHONUTF8=1 .venv/bin/python -I scripts/verify_demo_page.py /tmp/page.txt
   ```

   It must print "ALL NUMBERS ON THE PAGE MATCH THE RAW FILES." `page_text.py` finds Chrome or Edge;
   set `BROWSER=` to its path if it cannot.

## Step 2: Mac runs for the extra models (plugged in, overnight)

On the M4, tag search takes 9–22 s per item. So full accuracy runs for four more models (581 items × 3
tool conditions each) would take about a day. Run the **profiles only**: 100 items × 3 conditions per
model, about 1–2 hours in all.

1. Pull the models. Their digests must match `docs/VERSIONS.md`; if one differs, stop and tell
   Dev.

   ```bash
   ollama pull qwen2.5:1.5b && ollama pull gemma2:2b && ollama pull llama3.2:3b && ollama pull mistral:7b
   ```

2. Run the profiles:

   ```bash
   FINEVAL_RESULTS=results/mac/m4 PROFILE_ONLY=1 bash scripts/run_extra_models.sh 2>&1 | tee results/logs/extra_models_mac.log
   ```

   - The profiler writes to `$FINEVAL_RESULTS/profile/m4/`, i.e. `results/mac/m4/profile/m4/`, next
     to your earlier profiles. Check with `git status` that nothing new appears under
     `results/profile/`.
   - The script also re-runs `scorer_check_fincl.py` on the Windows outputs. Its output file should
     not change; if it does, tell Dev.
3. Optional, only if the Mac is free for a long time: run full accuracy for one condition only, for
   example tag search with numeric types:

   ```bash
   FINEVAL_RESULTS=results/mac/m4 .venv/bin/python -I -m fineval.run --model ollama:qwen2.5:1.5b --task concept_tagging --track tools_numeric --seed 0
   ```

   Then score it:

   ```bash
   FINEVAL_RESULTS=results/mac/m4 .venv/bin/python -I -m fineval.score --run qwen2.5-1.5b__concept_tagging__tools_numeric__s0
   ```

4. Rebuild the page (Step 1, items 3 and 4). The Mac cost block and the Mac accuracy table pick up new
   models and conditions by themselves.
   - `build_demo.py` asserts that each Mac score equals its stored score file.
   - `verify_demo_page.py` checks that every Mac score lies inside the Windows 95% interval. If one
     does not, the page sentence that says so is wrong: report it to Dev instead of editing the
     sentence.
5. Run `python -I scripts/compare_machines.py results/mac/m4` and update `results/mac/m4/README.md`.

## Step 3: Mac calculation (optional, overnight)

- The page shows calculation cost for Windows only, so a Mac accuracy check is enough here.
- Pick one model, for example Qwen2.5-7B, and run it with
  `FINEVAL_RESULTS=results/mac/m4 .venv/bin/python -I -m fineval.run --model ollama:qwen2.5:7b --task financial_calc --track tools --seed 0`
  (1,000 items, short prompts).
- Score it the same way, then compare it with the Windows score in CONTEXT.md.
- The page does not show Mac calculation yet. Report the comparison in `results/mac/m4/README.md`.

## Step 4: review the page and the proposal (1 hour)

- Open the page on a phone-width window. Check that every table scrolls rather than overflowing.
- Read `proposal/proposal.pdf` against CONTEXT.md. Every number in it must be in CONTEXT.md or on the
  page. Send Dev any wording changes; Dev rebuilds the PDF with tectonic.
- If GitHub Pages is live, open the live address and run `page_text.py` and `verify_demo_page.py` on it.

## Step 5: before the email (with Dev)

- Agree that the link can go to Prof. Liu (HOSTING.md: "no link goes to Prof. Liu until both of us
  agree").
- Dev sends the Reply-all with the proposal attached. You stay copied.
- Do **not** open the FINOS issue yet (`docs/FINOS_ISSUE_DRAFT.md`). It waits for the weekly meeting and
  Prof. Liu's answer about which repository and Space are live.

## Step 6: merge

- Push `stavan/next` and tell Dev.
- Dev reviews it, runs Step 1 on Windows, and merges it into `master`.
- After the merge, tag `v0.1`, but only if the page check passes on both machines.

## Who owns what now

| Dev (Windows) | Stavan (Mac) |
|---|---|
| `fineval/`, run scripts, `results/generations/`, `results/scores/`, `results/profile/`, calculation | `results/mac/`, Mac README, page review, hosting checks |
| Rebuilds the proposal PDF, sends the email | Reviews the proposal and the email draft |

`demo/`, `scripts/build_demo.py` and `scripts/verify_demo_page.py` are now shared. Tell the other person
before you change them.
