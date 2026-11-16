# Hosting proposal for the XBRL Leaderboard page

Status: proposal. Nothing is published yet, and no link goes to Prof. Liu until Dev and Stavan agree.

## What has to be hosted

The page is two static files, `demo/index.html` and `demo/data.js`. There is no server, no build step and
no database. `data.js` is written by `scripts/build_demo.py` from the saved model outputs.

## Proposal: GitHub Pages from this repository

- **Why:** the repository is already public, hosting is free, and the page is rebuilt from the same commit
  as the code and saved outputs. A reader can go from a number on the page to the file behind it.
- **Address:** `https://quantum-coded.github.io/xbrl-leaderboard/` (the default address for this
  repository).
- **How:** GitHub Pages can serve a branch root or `/docs`, but not `demo/` directly. So we add one
  workflow file that publishes `demo/` on every push to `master`.

  `.github/workflows/pages.yml`:

  ```yaml
  name: Publish demo page
  on:
    push:
      branches: [master]
      paths: ["demo/**"]
    workflow_dispatch:
  permissions:
    contents: read
    pages: write
    id-token: write
  concurrency:
    group: pages
    cancel-in-progress: true
  jobs:
    deploy:
      runs-on: ubuntu-latest
      environment:
        name: github-pages
        url: ${{ steps.deploy.outputs.page_url }}
      steps:
        - uses: actions/checkout@v4
        - uses: actions/upload-pages-artifact@v3
          with:
            path: demo
        - id: deploy
          uses: actions/deploy-pages@v4
  ```

- **Steps to switch it on** (repository owner):
  1. Merge the workflow file into `master`.
  2. In the repository settings, under Pages, set the source to "GitHub Actions".
  3. Push to `master`. The page appears at the address above.
- **The workflow file is not in the repository yet.** It is added only when we both agree to publish.
- **Check after each publish:** save the text of the live page and run
  `scripts/verify_demo_page.py` on it, the same check we run locally.

## Alternative: a static Hugging Face Space

- **Why consider it:** the group's Open Financial LLM Leaderboard is a Hugging Face Space, so an XBRL page
  there sits next to it.
- **How:** create a Space with the `static` SDK and copy `demo/index.html` and `demo/data.js` into it. The
  Space's `README.md` needs only `sdk: static` and a title in its header.
- **Cost:** the two files live in a second repository, so they must be copied after every rebuild, and the
  page is no longer tied to one commit. We also need to know which account or organisation should own it.

## Recommendation

Start with GitHub Pages. Move to, or mirror on, a Hugging Face Space if Prof. Liu wants the page under the
group's organisation.

## Before publishing

- **Licences of what the page shows.**
  - The page shows two FinTagging test items (a table row, the gold concept and a model answer).
    FinTagging's data is CC-BY-4.0 and its code is MIT, so this is allowed with attribution. The page
    names FinTagging as the source; a link to the dataset should be added before publishing.
  - Nothing from FinanceBench (CC-BY-NC) is in `demo/`. The filing-QA outputs are also kept out of the
    repository by `.gitignore`.
- **This repository has no `LICENSE` file.** We need to choose one before we ask others to reuse the code.
- **Questions for Prof. Liu:** should the page live under our repository or under the group's
  organisation, and who reviews changes to it?
