# The smallest FINOS leaderboard change for an XBRL tab (note, no PR yet)

**Repo:** `finos-labs/Open-Financial-LLMs-Leaderboard`, read at commit `0ebda4ed620a` (default branch
`main`, last push 2025-12-10). It is Apache-2.0.

## How it works today

**Stack.** A React frontend (`frontend/`), a FastAPI backend (`backend/app/`), and results stored as a
Hugging Face dataset.

**Data loading.** `backend/app/services/leaderboard.py` loads the dataset
`{HF_ORGANIZATION}/greek-contents`. At this commit, the code is the Greek-finance variant of the board.

**Task columns are hard-coded in two places.**
- The backend, in `leaderboard.py` (about lines 112–138). It holds a fixed dict
  `evaluations = {"multifin": ..., "qa": ..., "fns": ..., "finnum": ..., "fintext": ...}`. Each entry
  reads `"<Name> Raw"` and `"<Name>"` columns from the dataset row.
- The frontend, in `frontend/src/pages/LeaderboardPage/components/Leaderboard/constants/defaults.js`. It
  refers to the same `evaluations.*` keys, for example `evaluations.greek_average`.

**Stale contribution guide.** The README says to add tasks in `src/about.py`, but that file no longer
exists in this layout.

## Smallest useful change

1. **Config-driven task list.** Move the `evaluations` dict into a small config file, e.g.
   `backend/app/config/tasks.yaml`, with one entry per task: key, display name, raw column, normalised
   column, metric and category. `leaderboard.py` builds `evaluations` from it.
   - The backend change is about 30 lines.
   - The Greek board keeps working with its current config.
2. **One optional field per result: `tools`**, set to `none`, `tag_search_oracle` or `tag_search`.
   Results from agents or tools then never share a row with closed-book results.
3. **An XBRL config with one task:** FinCL accuracy on the public FinTagging subset, with our scores
   exported from `results/scores/` into the dataset's row format.
4. **Frontend.** Read the column list from the backend's `/leaderboard` response instead of
   `defaults.js`. Keep this as a second, separate step, because the frontend changes more code.

**Why this is small.**
- No new pages.
- No change to the existing Greek board.
- The XBRL board becomes one config file and one dataset.

## Before opening a PR

- Ask Prof. Liu's group which branch, Space and dataset are the live ones. The public Space
  `finosfoundation/Open-Financial-LLM-Leaderboard` may run different code from this repo.
- Agree the task config format with the maintainers in an issue first.
- Discuss it at the weekly meeting.
