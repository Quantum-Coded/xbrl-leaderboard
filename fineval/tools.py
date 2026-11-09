"""Tools for the tool-assisted track (Phase 6), all local and deterministic.

taxonomy_search  BM25 over FinTagging's US-GAAP 2024 index document (us_gaap_2024_BM25.jsonl),
                 optionally restricted to the entity's XBRL item type. FinTagging retrieves with
                 text-embedding-3-small (an API); BM25 is our documented local substitute.
formula_lookup   the formula and variable explanation for a named formula, from the XBRL-Agent
                 sheet (XBRL-Agent's "retriever" for formula questions).
safe_eval        arithmetic only: AST-whitelisted, no names except a few maths functions.
filing_search    BM25 over the pages of one FinanceBench filing (the "single store" setting).
"""
import ast
import json
import math
import re
from functools import lru_cache

from rank_bm25 import BM25Okapi

from .fetch import RAW

_TOKEN = re.compile(r"[a-z0-9]+")


def tokens(s: str) -> list:
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", str(s))       # split CamelCase element names
    return _TOKEN.findall(s.lower())


# ------------------------------------------------------------------ taxonomy
@lru_cache(maxsize=1)
def _taxonomy():
    p = RAW / "fintagging" / "taxonomy" / "us_gaap_2024_BM25.jsonl"
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    docs = [tokens(r["text"]) + tokens(r["us_gaap_tag"]) for r in rows]
    return rows, BM25Okapi(docs)


def taxonomy_search(query: str, k: int = 20, entity_type: str | None = None) -> list:
    """Top-k US-GAAP concepts as 'us-gaap:Name', best first."""
    rows, bm = _taxonomy()
    scores = bm.get_scores(tokens(query))
    idx = sorted(range(len(rows)), key=lambda i: (-scores[i], rows[i]["us_gaap_tag"]))
    out = []
    for i in idx:
        if entity_type and rows[i]["entity_type"] != entity_type:
            continue
        out.append("us-gaap:" + rows[i]["us_gaap_tag"])
        if len(out) == k:
            break
    return out


def fincl_query_text(inp: dict) -> str:
    """Retrieval query for a FinCL item: the context snippet inside the official query."""
    m = re.search(r"<context>(.*?)</context>", inp["query"], re.S)
    return (m.group(1) if m else inp["query"]).replace("|", " ")


def tag_query_text(inp: dict) -> str:
    return inp.get("concept_name") or inp["query"]


# ------------------------------------------------------------------ formulas
@lru_cache(maxsize=1)
def _formulas():
    import pandas as pd
    df = pd.read_excel(RAW / "xbrl_agent" / "Datasets" / "formulas_with_explanations_with_questions_with_gt.xlsx")
    return {str(r["Formula Name"]).strip().lower(): {"formula": str(r["Formula"]), "explanation": str(r["Explanation"])}
            for _, r in df.iterrows()}


def formula_lookup(name: str) -> dict | None:
    return _formulas().get(str(name).strip().lower())


# ------------------------------------------------------------------ safe arithmetic
_ALLOWED = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Call, ast.Name, ast.Load,
            ast.GeneratorExp, ast.ListComp, ast.comprehension, ast.List, ast.Tuple, ast.Store,
            ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.FloorDiv, ast.USub, ast.UAdd)
_FUNCS = {"sum": sum, "min": min, "max": max, "abs": abs, "round": round, "range": range, "len": len,
          "sqrt": math.sqrt, "log": math.log, "exp": math.exp, "pow": pow, "float": float}


def safe_eval(expr: str) -> float:
    tree = ast.parse(expr.strip(), mode="eval")
    loop_vars = {n.target.id for n in ast.walk(tree) if isinstance(n, ast.comprehension) and isinstance(n.target, ast.Name)}
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise ValueError(f"disallowed syntax: {type(node).__name__}")
        if isinstance(node, ast.Call) and not (isinstance(node.func, ast.Name) and node.func.id in _FUNCS):
            raise ValueError("disallowed call")
        if isinstance(node, ast.Name) and node.id not in _FUNCS and node.id not in loop_vars:
            raise ValueError(f"unknown name: {node.id}")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            raise ValueError("non-numeric constant")
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            e = node.right
            if isinstance(e, ast.Constant) and abs(e.value) > 1000:
                raise ValueError("exponent too large")
    return float(eval(compile(tree, "<expr>", "eval"), {"__builtins__": {}}, dict(_FUNCS)))


# ------------------------------------------------------------------ filings
CACHE = RAW.parent / "cache"


@lru_cache(maxsize=None)
def filing_pages(doc_name: str) -> list:
    """Page texts of a FinanceBench filing (0-indexed, as FinanceBench's evidence_page_num)."""
    cache = CACHE / "pages" / f"{doc_name}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    from pypdf import PdfReader
    pages = [(p.extract_text() or "") for p in PdfReader(RAW / "financebench" / "pdfs" / f"{doc_name}.pdf").pages]
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
    return pages


@lru_cache(maxsize=None)
def _filing_index(doc_name: str):
    return BM25Okapi([tokens(p) or ["_"] for p in filing_pages(doc_name)])


def filing_search(doc_name: str, query: str, k: int = 3) -> list:
    """Top-k (page_index, text) from one filing, best first."""
    pages = filing_pages(doc_name)
    scores = _filing_index(doc_name).get_scores(tokens(query))
    idx = sorted(range(len(pages)), key=lambda i: (-scores[i], i))[:k]
    return [(i, pages[i]) for i in idx]
