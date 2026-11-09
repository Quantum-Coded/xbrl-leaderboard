"""One loader per source file: raw file -> list of unified records.

Loaders copy source fields verbatim. Rows that cannot become a record (e.g. an empty question)
are returned in `skipped` with a reason, never dropped silently.
"""
import ast
import json
from functools import lru_cache

import pandas as pd

from ..fetch import RAW, load_manifest, sha256
from ..normalize import strip_enum
from ..schema import Record
from .registry import SOURCES

METRIC = {
    "concept_tagging": "concept_exact@v1",
    "fact_extraction": "finni_pair_f1@v1",
    "financial_calc": "numeric_match@v1",
    "filing_qa": "qa_judge@v1",
    "terminology": "term_judge@v1",
}


@lru_cache(maxsize=None)
def checked(key: str):
    """Path of a pinned raw file, after confirming its hash matches the manifest."""
    rec = load_manifest().get(key)
    if rec is None:
        raise FileNotFoundError(f"{key} is not in data/raw/MANIFEST.json; run python -I -m fineval.fetch")
    p = RAW / key
    if sha256(p) != rec["sha256"]:
        raise ValueError(f"{key}: hash differs from the manifest")
    return p, rec["sha256"]


def _blank(v) -> bool:
    return v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == ""


def _s(v):
    """Cell value as it should be stored: None for blanks, Python scalars otherwise."""
    if _blank(v):
        return None
    return v.item() if hasattr(v, "item") else v


class Out:
    def __init__(self):
        self.records, self.skipped = [], []

    def add(self, *, source, subset, sid, split, task, inp, gold, key, row, filing_key=None, meta=None):
        p, digest = checked(key)
        self.records.append(Record(
            uid=f"{source}:{subset}:{split}:{sid}", source=source, subset=subset, source_id=str(sid),
            source_split=split, task=task, input=inp, gold=gold, metric=METRIC[task],
            licence=SOURCES[source]["licence"], provenance={"file": key, "row": row, "sha256": digest},
            filing_key=filing_key, meta=meta or {}))

    def skip(self, key, row, reason):
        self.skipped.append({"file": key, "row": row, "reason": reason})


# ------------------------------------------------------------------ FinanceBench
def financebench(out: Out):
    key = "financebench/data/financebench_open_source.jsonl"
    p, _ = checked(key)
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
        r = json.loads(line)
        out.add(source="financebench", subset="open", sid=r["financebench_id"], split="test", task="filing_qa",
                inp={"question": r["question"], "company": r["company"], "doc_name": r["doc_name"]},
                gold={"answer": r["answer"], "justification": r.get("justification"),
                      "evidence": [{"doc_name": e.get("doc_name"), "page": e.get("evidence_page_num"),
                                    "text": e.get("evidence_text")} for e in r.get("evidence") or []]},
                key=key, row=i, filing_key=r["doc_name"],
                meta={"question_type": r.get("question_type"), "question_reasoning": r.get("question_reasoning")})


# ------------------------------------------------------------------ XBRL-Agent
def xbrl_agent(out: Out):
    key = "xbrl_agent/Datasets/XBRL Terminology.xlsx"
    df = pd.read_excel(checked(key)[0])
    for i, r in df.iterrows():
        if _blank(r["Term"]) or _blank(r["Explanation"]):
            out.skip(key, int(i), "empty term or explanation")
            continue
        note = _s(r.get("Unnamed: 3")) or _s(r.get("Unnamed: 2"))
        out.add(source="xbrl_agent", subset="terminology", sid=int(i), split="test", task="terminology",
                inp={"term": str(r["Term"])}, gold={"definition": str(r["Explanation"])}, key=key, row=int(i),
                meta={"source_note": note} if note else None)

    key = "xbrl_agent/Datasets/formulas_with_explanations_with_questions_with_gt.xlsx"
    df = pd.read_excel(checked(key)[0])
    for i, r in df.iterrows():
        for q in range(1, 21):
            qtext, ans = r[f"Question {q}"], r[f"Answer {q}"]
            if _blank(qtext) or _blank(ans):
                out.skip(key, int(i), f"formula {r['Formula Name']!r}: question {q} or its answer is empty")
                continue
            out.add(source="xbrl_agent", subset="formula", sid=f"{i}-{q}", split="test", task="financial_calc",
                    inp={"question": strip_enum(qtext), "formula_name": str(r["Formula Name"]),
                         "formula": _s(r["Formula"]), "explanation": _s(r["Explanation"])},
                    gold={"value": float(ans)}, key=key, row=int(i), meta={"question_no": q})

    key = "xbrl_agent/Datasets/financebench.xlsx"
    df = pd.read_excel(checked(key)[0])
    for i, r in df.iterrows():
        out.add(source="xbrl_agent", subset="financebench", sid=r["financebench_id"], split="test", task="filing_qa",
                inp={"question": str(r["question"]), "doc_name": str(r["doc_name"])},
                gold={"answer": str(r["answer"]), "evidence": [{"doc_name": str(r["doc_name"]),
                      "page": _s(r["page_number"]), "text": _s(r["evidence_text"])}]},
                key=key, row=int(i), filing_key=str(r["doc_name"]))


# ------------------------------------------------------------------ COLING Regulations Challenge (Task 7)
_C = "coling/{split_dir}/Task7-XBRL/"


def coling(out: Out):
    for split, d in (("test", "testing"), ("validation", "validation")):
        base = _C.format(split_dir=d)

        key = base + f"Task7-XBRL Terminology-{d}.csv"
        for i, r in pd.read_csv(checked(key)[0]).iterrows():
            if _blank(r["Term"]) or _blank(r["Explanation"]):
                out.skip(key, int(i), "empty term or explanation")
                continue
            out.add(source="coling", subset="terminology", sid=int(i), split=split, task="terminology",
                    inp={"term": str(r["Term"])}, gold={"definition": str(r["Explanation"])}, key=key, row=int(i))

        key = base + f"Task7-XBRL-domain_numberic_query-{d}.csv"
        for i, r in pd.read_csv(checked(key)[0]).iterrows():
            if _blank(r["question"]) or _blank(r["answer"]):
                out.skip(key, int(i), "empty question or answer")
                continue
            out.add(source="coling", subset="domain_numeric", sid=r["financebench_id"], split=split, task="filing_qa",
                    inp={"question": str(r["question"]), "doc_name": str(r["doc_name"])},
                    gold={"answer": str(r["answer"]), "evidence": [{"doc_name": str(r["doc_name"]),
                          "page": _s(r["page_number"]), "text": _s(r["evidence_text"])}]},
                    key=key, row=int(i), filing_key=str(r["doc_name"]), meta={"question_type": _s(r["question_type"])})

        key = base + f"Task7-XBRL-Tag_Query_to_XBRL_Reports-{d}.csv"
        for i, r in pd.read_csv(checked(key)[0]).iterrows():
            tags = ast.literal_eval(r["xbrl_tag"]) if str(r["xbrl_tag"]).startswith("[") else [str(r["xbrl_tag"])]
            filing = str(r["doc_path"]).split("/")[0]
            out.add(source="coling", subset="tag_query", sid=int(i), split=split, task="concept_tagging",
                    inp={"query": str(r["query"]), "company": _s(r["{company name}"]),
                         "period": _s(r["{fiscal year/quarter}"]), "concept_name": _s(r["{financial concept}"])},
                    gold={"concepts": sorted(set(tags))}, key=key, row=int(i),
                    filing_key=f"{str(r['ticker']).upper()}|{filing}")

    key = "coling/testing/Task7-XBRL/Task7-XBRL-financial_math-testing.tsv"
    for i, r in pd.read_csv(checked(key)[0], sep="\t").iterrows():
        out.add(source="coling", subset="math", sid=int(i), split="test", task="financial_calc",
                inp={"question": strip_enum(r["Question"]), "formula_name": str(r["Formula Name"]),
                     "formula": _s(r["Formula"]), "explanation": _s(r["Explanation"])},
                gold={"value": float(r["Answer"])}, key=key, row=int(i))

    key = "coling/validation/Task7-XBRL/Task7-XBRL-financial_math-validation.csv"
    for i, r in pd.read_csv(checked(key)[0]).iterrows():
        for q in range(1, 21):
            if _blank(r[f"Question {q}"]) or _blank(r[f"Answer {q}"]):
                out.skip(key, int(i), f"question {q} or its answer is empty")
                continue
            out.add(source="coling", subset="math", sid=f"{i}-{q}", split="validation", task="financial_calc",
                    inp={"question": strip_enum(r[f"Question {q}"]), "formula_name": str(r["Formula Name"]),
                         "formula": _s(r["Formula"]), "explanation": _s(r["Explanation"])},
                    gold={"value": float(r[f"Answer {q}"])}, key=key, row=int(i), meta={"question_no": q})


# ------------------------------------------------------------------ FinTagging
def _facts(answer: str):
    d = json.loads(answer)
    items = d.get("result", d.get("results", []))
    return [{"fact": str(x["Fact"]), "type": str(x["Type"])} for x in items]


def fintagging(out: Out):
    key = "fintagging/subdata/FinCL-eval-subset.csv"
    for i, r in pd.read_csv(checked(key)[0]).iterrows():
        out.add(source="fintagging", subset="fincl_subset", sid=int(i), split="test", task="concept_tagging",
                inp={"query": str(r["query"]), "entity": str(r["entity"]), "entity_type": str(r["entity_type"]),
                     "category": str(r["category"]), "context": str(r["context"])},
                gold={"concepts": [str(r["answer"])]}, key=key, row=int(i))

    key = "fintagging/subdata/FinNI-eval-subset.csv"
    for i, r in pd.read_csv(checked(key)[0]).iterrows():
        out.add(source="fintagging", subset="finni_subset", sid=int(r["context_index"]), split="test",
                task="fact_extraction", inp={"context": str(r["context"]), "query": str(r["query"])},
                gold={"facts": _facts(r["answer"])}, key=key, row=int(i))

    key = "fintagging/annotation/TrainingSet_Annotation.json"
    data = json.loads(checked(key)[0].read_text(encoding="utf-8"))
    for kind in ("text_data", "table_data"):
        for i, r in enumerate(data[kind]):
            ents = r.get("numeric_entities") or []
            out.add(source="fintagging", subset="train_" + kind.split("_")[0], sid=i, split="train",
                    task="fact_extraction", inp={"context": r["text"]},
                    gold={"facts": [{"fact": str(e["value"]), "type": str(e["type"])} for e in ents],
                          "concepts": [str(e["concept"]) for e in ents]},
                    key=key, row=i)


LOADERS = {"financebench": financebench, "xbrl_agent": xbrl_agent, "coling": coling, "fintagging": fintagging}


def load_all():
    out = Out()
    for fn in LOADERS.values():
        fn(out)
    return out
