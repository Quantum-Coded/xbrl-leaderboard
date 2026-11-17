# Draft issue for `finos-labs/Open-Financial-LLMs-Leaderboard` (not opened)

Status: draft. Do not open it until Prof. Liu and the weekly meeting agree (see `FINOS_INTEGRATION.md`).
Checked against commit `0ebda4ed620a` (still the head of `main` on 18 Nov 2026). The repository's open
issues are the weekly meeting notes; none covers task configuration.

---

**Title:** Make the leaderboard's task list configurable (README points to a file that no longer exists)

**Body:**

The README's "add a new task" instructions point to `src/about.py`, which is not in the current layout.
Today the tasks are hard-coded in several places:

- `backend/app/services/leaderboard.py` (about lines 112–138): a fixed `evaluations` dict
  (`multifin`, `qa`, `fns`, `finnum`, `fintext`), each reading `"<Name> Raw"` and `"<Name>"` columns.
- The dataset name: `AGGREGATED_REPO` in `backend/app/config/hf_config.py`, and two strings in
  `leaderboard.py`.
- The frontend, in four files under `frontend/src/pages/LeaderboardPage/components/Leaderboard/`:
  `constants/defaults.js`, `context/LeaderboardContext.js`, `utils/columnUtils.js` and
  `hooks/useDataUtils.js`.

So adding a task group (we are building one for XBRL tasks: FinTagging concept linking and XBRL-Agent
calculation) means editing all of these.

**Proposal**

1. A small task config file, for example `backend/app/config/tasks.yaml`, with one entry per task: key,
   display name, raw column, normalised column, metric and category, plus the dataset name.
   `leaderboard.py` builds `evaluations` from it. The current Greek board keeps working with its own
   config.
2. An optional `tools` field per result (for example `none` or `tag_search`), included in the row id
   built in `transform_data` (line 110). Without it, two results for the same model with and without
   tools get the same id.
3. Later, as a separate change: the frontend reads the column list from the `/leaderboard` response
   instead of the four files above.

Would the maintainers accept this direction? If so, we can send step 1 and 2 as one small PR, with DCO
sign-off and Apache-2.0 headers as `CONTRIBUTING.md` asks, and update the README's instructions in the
same PR.

**Questions**

- Which code runs the public Space `finosfoundation/Open-Financial-LLM-Leaderboard`? This repository
  loads `TheFinAI/greek-contents`.
- Is a YAML file the preferred format, or should the config live in Python?
