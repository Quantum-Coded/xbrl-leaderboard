"""Phase 9: the site shows only numbers that come from files.

The in-browser check (every number rendered on every page is a formatted value of the exported
JSON) is run against `npm run preview`; see docs/protocol.md. These tests cover the static side.
"""
import json
import re

from fineval import export
from fineval.build import OUT
from fineval.fetch import ROOT

APP = ROOT / "site" / "src" / "App.tsx"


def _site(name):
    return json.loads((export.SITE / f"{name}.json").read_text(encoding="utf-8"))


def test_export_is_deterministic():
    export.main()
    before = {p.name: p.read_bytes() for p in export.SITE.glob("*.json")}
    export.main()
    assert before == {p.name: p.read_bytes() for p in export.SITE.glob("*.json")}


def test_published_values_match_reference_file():
    pub = json.loads((ROOT / "reference" / "published.json").read_text(encoding="utf-8"))
    for r in _site("published"):
        block = next(b for (b, m, t, *_ ) in export.PUBLISHED_MAP if m == r["metric"] and t == r["task"])
        b = pub[block]
        model = r["model"] + (f" | {r['setting']}" if r["setting"] else "")
        assert b["rows"][model][b["metrics"].index(r["metric"])] == r["raw"]


def test_dataset_numbers_match_build():
    assert _site("datasets")["summary"] == json.loads((OUT / "summary.json").read_text(encoding="utf-8"))


def test_no_hard_coded_figures_in_page_text():
    src = APP.read_text(encoding="utf-8")
    texts = re.findall(r">([^<>{}]+)<", src)
    prose = [t for t in texts if not re.search(r"[();=\[\]]", t) and re.search(r"[A-Za-z]{2,}", t)]
    assert len(prose) > 40                          # the filter still sees the page copy
    offenders = [t.strip() for t in prose if re.search(r"\d", t.replace("FinEval v1", ""))]
    assert offenders == []
