"""Every published number in reference/published.json appears on the cited page of the paper."""
import json
import re

from fineval.fetch import ROOT

PUB = json.loads((ROOT / "reference" / "published.json").read_text(encoding="utf-8"))


def _page(path, n):
    text = (ROOT / path).read_text(encoding="utf-8")
    parts = re.split(r"=== PAGE (\d+) ===", text)
    return dict(zip(map(int, parts[1::2]), parts[2::2]))[n]


def test_every_published_number_is_on_its_page():
    checked = 0
    for name, block in PUB.items():
        if name.startswith("_") or not block.get("paper_file"):
            continue
        page = _page(block["paper_file"], block["page"])
        assert block["table"] in page
        for model, vals in block["rows"].items():
            assert model.split(" | ")[0].split(" (")[0] in page, (name, model)
            for v in vals:
                token = f"{v} (" if isinstance(v, int) else f"{v:.4f}"
                assert token in page, (name, model, v)
                checked += 1
    assert checked > 100
