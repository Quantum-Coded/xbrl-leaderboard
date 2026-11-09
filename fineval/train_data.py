"""Supervised fine-tuning data for Phase 7, from FinTagging's released training set only.

    python -I -m fineval.train_data

Inputs are the `train` split built in Phase 4, which already excludes every cluster that touches
test, every conflicting item, and every near-duplicate of an eval item. Two formats are written:

  finni.jsonl  FinNI style: the official FinNI instruction (identical for all items, so it is not
               test content) + a training context -> {"result": [{"Fact", "Type"}]}
  fincl.jsonl  FinCL style: one example per tagged entity, in FinCL's query format
               ("<category>: <entity> v </entity> <entity type> t </entity type> <context> row </context>")
               -> {"result": "us-gaap:Concept"}

A final check re-asserts that no training context contains a FinNI test context, and drops any
FinCL training example whose query equals a FinCL test query (counted in stats.json).
"""
import html
import json
import re
from functools import lru_cache

from . import data
from .build import OUT
from .normalize import text_key
from .prompts import FINCL_INSTRUCTION

SFT = OUT / "sft"


def finni_instruction() -> tuple:
    """(prefix, suffix) of the FinNI prompt, taken from the eval prompt template."""
    pre = set()
    suf = set()
    for it in data.items("fact_extraction"):
        q, c = it["input"]["query"], it["input"]["context"]
        k = q.find(c)
        if k > 0:
            pre.add(q[:k])
            suf.add(q[k + len(c):])
    if len(pre) != 1 or len(suf) != 1:
        raise ValueError("FinNI prompts do not share one template")
    return pre.pop(), suf.pop()


@lru_cache(maxsize=4096)
def _rows(table_html: str) -> list:
    rows = []
    for tr in re.findall(r"<tr>(.*?)</tr>", table_html, re.S):
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<td>(.*?)</td>", tr, re.S)]
        cells = [c for c in cells if c]
        if cells:
            rows.append(" | ".join(cells))
    return rows


@lru_cache(maxsize=4096)
def _row_cells(table_html: str) -> tuple:
    return tuple((row, frozenset(c.replace(",", "").replace("(", "").replace(")", "").strip() for c in row.split("|")))
                 for row in _rows(table_html))


def _fincl_context(item, value: str):
    """The sentence or table row that contains the value, as in FinCL's query context."""
    text = item["input"]["context"]
    if item["subset"] == "train_table":
        for row, cells in _row_cells(text):
            if value in cells:
                return "table", row
        return "table", None
    for sent in re.split(r"(?<=[.;])\s+", text):
        if value in sent.replace(",", ""):
            return "text", sent.strip()
    return "text", None


def build():
    pre, suf = finni_instruction()
    train = data.items("fact_extraction", "train")
    finni, fincl, no_ctx = [], [], 0
    for it in train:
        facts = it["gold"]["facts"]
        finni.append({"uid": it["uid"], "prompt": pre + it["input"]["context"] + suf,
                      "completion": json.dumps({"result": [{"Fact": f["fact"], "Type": f["type"]} for f in facts]})})
        for f, concept in zip(facts, it["gold"]["concepts"]):
            cat, ctx = _fincl_context(it, f["fact"])
            if ctx is None:
                no_ctx += 1
                continue
            q = (f"{cat}: <entity> {f['fact']} </entity> <entity type> {f['type']} </entity type> "
                 f"<context> {ctx} </context>")
            fincl.append({"uid": it["uid"], "query": q, "prompt": f"{FINCL_INSTRUCTION}\n\nInput Query: {q}\nAnswer:",
                          "completion": json.dumps({"result": concept})})

    # leakage re-check: no training context contains a FinNI test context, and no FinCL training
    # query equals a FinCL test query (same value, type and row)
    test_ctx = [t for t in (text_key(i["input"]["context"]) for i in data.items("fact_extraction")) if len(t) >= 40]
    for it in train:
        k = text_key(it["input"]["context"])
        if any(t in k for t in test_ctx):
            raise ValueError(f"training context {it['uid']} contains a FinNI test context")
    test_q = {text_key(i["input"]["query"]) for i in data.items("concept_tagging") if i["subset"] == "fincl_subset"}
    leaked = [ex for ex in fincl if text_key(ex["query"]) in test_q]
    fincl = [ex for ex in fincl if text_key(ex["query"]) not in test_q]

    SFT.mkdir(parents=True, exist_ok=True)
    for name, rows in (("finni", finni), ("fincl", fincl)):
        with (SFT / f"{name}.jsonl").open("w", encoding="utf-8", newline="\n") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    stats = {"train_items": len(train), "finni_examples": len(finni), "fincl_examples": len(fincl),
             "fincl_dropped_equal_to_test_query": len(leaked),
             "fincl_entities_without_locatable_context": no_ctx}
    (SFT / "stats.json").write_text(json.dumps(stats, indent=1), encoding="utf-8")
    return stats


if __name__ == "__main__":
    print(json.dumps(build(), indent=1))
