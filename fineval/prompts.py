"""Prompts per task and track. `build(item, track)` returns (system, user, tool_log).

closed  the model alone. Official prompts are used verbatim where the source publishes one
        (FinNI query, COLING tag query); otherwise a minimal instruction plus the question.
tools   the same models with local tools: BM25 candidate concepts (tagging), BM25-retrieved
        formula + a calculator the model calls by writing an expression (calculation), BM25-
        retrieved filing pages (filing QA). FinNI has no tool variant (the context is given).
"""
import re

from . import tools

TRACKS = ("closed", "tools")
TAG_CANDIDATES = 100
FILING_PAGES = 3
PAGE_CHARS = 3500          # per retrieved page, so three pages fit a 4k-token context with the question

FINCL_INSTRUCTION = (
    "You are an XBRL tagging expert. Map the numerical entity below to the single most appropriate "
    "US-GAAP 2024 taxonomy concept, given its type and context. "
    'Reply only with JSON: {"result": "us-gaap:ConceptName"}')

CALC_CLOSED = ("Solve the financial calculation. Show brief working, then end with a final line "
               "'Answer: <number>' (a plain number, no units or currency symbols).")
CALC_TOOLS = ("Solve the financial calculation with the help of the reference formula. Do not compute by hand: "
              "write ONE Python arithmetic expression that computes the answer (numbers, + - * / **, "
              "sum(... for t in range(a, b)), min, max, abs, round, sqrt, log, exp only; no variable names). "
              "Reply with exactly one line: 'Expression: <expression>'.")

QA_CLOSED = "Answer the question about the company's SEC filing concisely. If you cannot answer, say so."
QA_TOOLS = ("Answer the question using the filing pages provided. Be concise and give the figure or fact "
            "asked for. If the pages do not contain the answer, say so.")


def _candidates_block(cands):
    return "Candidate Tags: [" + ", ".join(f'"{c}"' for c in cands) + "]"


def build(item: dict, track: str) -> tuple:
    task, inp, sub = item["task"], item["input"], item["subset"]
    log = {}
    if task == "concept_tagging":
        if sub == "fincl_subset":
            user = f"{FINCL_INSTRUCTION}\n\nInput Query: {inp['query']}"
            if track == "tools":
                c = tools.taxonomy_search(tools.fincl_query_text(inp), k=TAG_CANDIDATES, entity_type=inp["entity_type"])
                log["candidates"] = c
                user += "\n" + _candidates_block(c) + "\nChoose one tag from the candidates."
            return None, user + "\nAnswer:", log
        user = inp["query"]
        if track == "tools":
            c = tools.taxonomy_search(tools.tag_query_text(inp), k=TAG_CANDIDATES)
            log["candidates"] = c
            user += "\n" + _candidates_block(c) + "\nChoose one tag from the candidates."
        return None, user, log

    if task == "fact_extraction":
        return None, inp["query"], log

    if task == "financial_calc":
        q = inp["question"]
        if track == "closed":
            return CALC_CLOSED, q, log
        f = formula_search(q)
        log["formula"] = f
        ref = f"Reference formula ({f['name']}): {f['formula']}\nVariables: {f['explanation']}" if f else "No formula found."
        return CALC_TOOLS, f"{ref}\n\nQuestion: {q}", log

    if task == "filing_qa":
        head = f"Company filing: {inp['doc_name']}\nQuestion: {inp['question']}"
        if track == "closed":
            return QA_CLOSED, head, log
        hits = tools.filing_search(inp["doc_name"], inp["question"], k=FILING_PAGES)
        log["pages"] = [p for p, _ in hits]
        ctx = "\n\n".join(f"[Page {p}]\n{t[:PAGE_CHARS]}" for p, t in hits)
        return QA_TOOLS, f"{ctx}\n\n{head}", log

    raise ValueError(f"no prompt for task {task}")


def formula_search(question: str):
    """BM25 over XBRL-Agent formula name + formula + explanation, queried with the question text.
    Index fields were fixed once and are not tuned on test questions; retrieval_eval reports the
    resulting accuracy as the tool track's ceiling."""
    f = tools._formulas()
    names = sorted(f)
    s = _formula_index().get_scores(tools.tokens(question))
    best = max(range(len(names)), key=lambda i: (s[i], -i))
    if s[best] <= 0:
        return None
    return {"name": names[best], **f[names[best]]}


_FORMULA_BM25 = []


def _formula_index():
    if not _FORMULA_BM25:
        from rank_bm25 import BM25Okapi
        f = tools._formulas()
        _FORMULA_BM25.append(BM25Okapi([tools.tokens(f"{n} {f[n]['formula']} {f[n]['explanation']}") for n in sorted(f)]))
    return _FORMULA_BM25[0]


def extract_expression(text: str):
    m = re.search(r"Expression\s*:\s*`*([^\n`]+)", text, re.I)
    return m.group(1).strip() if m else None


def finish_tools_calc(text: str) -> tuple:
    """Evaluate the model's expression; returns (answer_text, log)."""
    expr = extract_expression(text)
    if not expr:
        return text, {"expression": None, "error": "no expression"}
    try:
        v = tools.safe_eval(expr)
        return f"{text}\nAnswer: {v}", {"expression": expr, "value": v}
    except Exception as e:                          # malformed or disallowed expression = wrong answer
        return text, {"expression": expr, "error": f"{type(e).__name__}: {e}"}
