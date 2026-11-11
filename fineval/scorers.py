"""Versioned scorers, one per metric id (Phase 5). Each returns a dict of named variants in [0, 1]
(or counts for F1-type metrics); the first key is the primary variant. Gold text is never edited:
normalisation happens only on copies inside these functions.

concept_exact@v1  FinCL / tag query. Primary `exact` = predicted concept string equals a gold
                  concept, as in FinTagging's calculate_acc (evaluate_NEN.ipynb). `ci_element`
                  ignores case and the "us-gaap:" prefix (sensitivity).
finni_pair_f1@v1  FinNI. Multiset match of (Fact, Type) pairs; `strict` compares the fact text
                  verbatim (trimmed), `numeric` compares fact values as numbers. Returns tp/fp/fn;
                  micro P/R/F1 are pooled over items by `aggregate`.
numeric_match@v1  financial calculation. Primary `final` = a number in the answer's final segment
                  matches gold to 2 decimals or within 1% relative error, with % read as /100 when
                  gold is a fraction. `unit_agnostic` also accepts x100 / /100 forms (sensitivity),
                  `last_number` uses only the last number.
"""
import json
import re

from .normalize import parse_number

# ------------------------------------------------------------------ concept tagging
_CONCEPT = re.compile(r"\b(?:([a-z][a-z0-9-]*)\s*[:_]\s*)?([A-Z][A-Za-z0-9]{2,})\b")


def parse_concept(out: str) -> str | None:
    """The concept a model answered with: JSON {"result": ...}, 'Answer: us-gaap:X', or the
    first prefixed/CamelCase element name in the text."""
    t = out.strip()
    m = re.search(r"\{\s*\"result\"\s*:\s*\"([^\"]+)\"", t)
    if m:
        return m.group(1).strip()
    m = re.search(r"answer\s*[:：]\s*([A-Za-z-]+\s*:\s*[A-Za-z0-9]+|[A-Z][A-Za-z0-9]+)", t, re.I)
    if m:
        return re.sub(r"\s+", "", m.group(1))
    m = re.search(r"\b[a-z][a-z0-9-]*:[A-Z][A-Za-z0-9]+\b", t)
    if m:
        return m.group(0)
    m = _CONCEPT.search(t)
    return m.group(0).replace(" ", "") if m else None


def _element(c: str) -> str:
    return c.split(":")[-1].strip().lower()


def concept_exact(out: str, gold: dict) -> dict:
    p = parse_concept(out)
    golds = gold["concepts"]
    return {"exact": float(p is not None and p in golds),
            "ci_element": float(p is not None and _element(p) in {_element(g) for g in golds})}


# ------------------------------------------------------------------ FinNI
def _facts(items) -> list:
    return [(str(x.get("Fact", "")).strip(), str(x.get("Type", "")).strip()) for x in items if isinstance(x, dict)]


def parse_facts(out: str, strict: bool = False) -> list | None:
    """List of (fact, type) from a FinNI answer; None when no JSON result can be parsed.

    The FinNI instruction asks for {"result": [...]}. A bare JSON list of {"Fact", "Type"} objects is
    also accepted (same content, missing wrapper); `strict=True` accepts only the requested wrapper,
    which is reported as the `format_ok` variant.
    """
    t = out.strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", t, re.S)
    cand = [m.group(1)] if m else []
    cand += re.findall(r"\{\s*\"results?\"\s*:\s*\[.*?\]\s*\}", t, re.S)
    for c in cand:
        try:
            d = json.loads(c)
        except json.JSONDecodeError:
            continue
        items = d.get("result", d.get("results"))
        if isinstance(items, list):
            return _facts(items)
    if strict:
        return None
    dec = json.JSONDecoder()
    for k in [i for i, ch in enumerate(t) if ch == "["][:50]:     # linear scan; no backtracking regex
        try:
            d, _ = dec.raw_decode(t, k)
        except json.JSONDecodeError:
            continue
        if isinstance(d, list) and all(isinstance(x, dict) and "Fact" in x for x in d):
            return _facts(d)
    return None


def _num_or_text(fact: str):
    v = parse_number(fact.replace(" ", ""))
    return f"{v:.10g}" if v is not None else fact.strip().lower()


def _match(pred, gold, key):
    g = [key(x) for x in gold]
    tp = 0
    for x in (key(p) for p in pred):
        if x in g:
            g.remove(x)
            tp += 1
    return tp, len(pred) - tp, len(gold) - tp


def finni_pairs(out: str, gold: dict) -> dict:
    pred = parse_facts(out)
    goldp = [(f["fact"].strip(), f["type"].strip()) for f in gold["facts"]]
    parsed = pred is not None
    pred = pred or []
    s = _match(pred, goldp, lambda x: x)
    n = _match(pred, goldp, lambda x: (_num_or_text(x[0]), x[1]))
    return {"strict_tp": s[0], "strict_fp": s[1], "strict_fn": s[2],
            "numeric_tp": n[0], "numeric_fp": n[1], "numeric_fn": n[2], "parsed": float(parsed),
            "format_ok": float(parse_facts(out, strict=True) is not None)}


def prf(tp, fp, fn) -> dict:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": p, "recall": r, "f1": 2 * p * r / (p + r) if p + r else 0.0}


# ------------------------------------------------------------------ numeric answers
_NUM = re.compile(r"(-)?\$?\(?(\d[\d,]*\.?\d*|\.\d+)\)?\s*(%|percent|million|billion|thousand)?", re.I)
_SCALE = {"thousand": 1e3, "million": 1e6, "billion": 1e9}


def numbers(text: str) -> list:
    vals = []
    for m in _NUM.finditer(text):
        try:
            v = float(m.group(2).replace(",", "").rstrip("."))
        except ValueError:
            continue
        unit = (m.group(3) or "").lower()
        v *= _SCALE.get(unit, 1)
        neg = bool(m.group(1)) or m.group(0).lstrip("$").startswith("(")
        vals.append((-v if neg else v, unit))
    return vals


def final_segment(out: str) -> str:
    m = list(re.finditer(r"(final answer|answer is|answer:|therefore|thus|so,|=)", out, re.I))
    return out[m[-1].start():] if m else out


def num_match(v: float, unit: str, gold: float) -> bool:
    cands = [v]
    if unit in ("%", "percent") and abs(gold) < 1.5:
        cands.append(v / 100)
    for c in cands:
        if round(c, 2) == round(gold, 2) or (gold != 0 and abs(c - gold) / abs(gold) <= 0.01):
            return True
    return False


def numeric_match(out: str, gold: dict) -> dict:
    g = float(gold["value"])
    fin, allnums = numbers(final_segment(out)), numbers(out)
    return {"final": float(any(num_match(v, u, g) for v, u in fin)),
            "unit_agnostic": float(any(num_match(c, "", g) for v, _ in fin for c in (v, v / 100, v * 100))),
            "last_number": float(bool(allnums) and num_match(*allnums[-1], g))}


SCORERS = {"concept_exact@v1": concept_exact, "finni_pair_f1@v1": finni_pairs, "numeric_match@v1": numeric_match}


def score(metric: str, out: str, gold: dict) -> dict:
    return SCORERS[metric](out, gold)


def aggregate(metric: str, rows: list) -> dict:
    """Task-level scores from per-item score dicts."""
    if not rows:
        return {}
    if metric == "finni_pair_f1@v1":
        agg = {}
        for v in ("strict", "numeric"):
            tp, fp, fn = (sum(r[f"{v}_{k}"] for r in rows) for k in ("tp", "fp", "fn"))
            agg.update({f"{v}_{k}": x for k, x in prf(tp, fp, fn).items()})
        agg["parsed"] = sum(r["parsed"] for r in rows) / len(rows)
        agg["format_ok"] = sum(r.get("format_ok", 0) for r in rows) / len(rows)
        return agg
    return {k: sum(r[k] for r in rows) / len(rows) for k in rows[0]}
