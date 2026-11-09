"""Normalisation used for duplicate detection and answer comparison. Gold text is never rewritten;
these functions only produce comparison keys."""
import hashlib
import re
import unicodedata

_ENUM = re.compile(r"^\s*\d+\s*[.)]\s*")              # "12. " prefix on XBRL-Agent / COLING questions
_NUM = re.compile(r"(?<![\w.])-?\$?\(?\d[\d,]*(?:\.\d+)?\)?%?")
_SPACE = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s.%-]")


def text_key(s) -> str:
    """Canonical text for matching: NFKC, lowercase, no enumeration prefix or wrapping quotes,
    numbers without thousands separators or currency signs, punctuation dropped, spaces collapsed."""
    s = unicodedata.normalize("NFKC", str(s))
    s = _ENUM.sub("", s.strip()).strip().strip('"').strip("'").strip()
    s = s.lower()
    s = _NUM.sub(lambda m: canon_number_str(m.group(0)), s)
    s = _PUNCT.sub(" ", s)
    s = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", s)          # sentence dots, but keep decimal points
    return _SPACE.sub(" ", s).strip()


def exact_hash(s) -> str:
    return hashlib.sha1(text_key(s).encode("utf-8")).hexdigest()


def parse_number(s):
    """Parse '$1,577.00', '(12.5)', '41%', '1577' to float; None if `s` is not a single number."""
    if isinstance(s, (int, float)):
        return float(s)
    t = unicodedata.normalize("NFKC", str(s)).strip()
    m = re.fullmatch(r"(-)?\s*\$?\s*(\()?\s*\$?\s*(\d[\d,]*(?:\.\d+)?|\.\d+)\s*(\))?\s*(%)?", t)
    if not m:
        return None
    neg, lp, digits, rp, pct = m.groups()
    if bool(lp) != bool(rp):
        return None
    v = float(digits.replace(",", ""))
    return -v if (neg or lp) else v


def canon_number_str(tok: str) -> str:
    pct = tok.endswith("%")
    v = parse_number(tok)
    if v is None:
        return tok
    out = f"{v:.10g}"
    return out + ("%" if pct else "")


def numbers_in(s) -> tuple:
    """Sorted multiset of the numbers in a text; used so templated questions that differ only in
    their numbers are never treated as duplicates."""
    vals = []
    for m in _NUM.finditer(unicodedata.normalize("NFKC", str(s))):
        v = parse_number(m.group(0).rstrip("%"))
        if v is not None:
            vals.append(round(v, 6))
    return tuple(sorted(vals))


def strip_enum(s) -> str:
    """Question text without the '12. "..."' wrapper used in XBRL-Agent / COLING formula sheets."""
    return _ENUM.sub("", str(s).strip()).strip().strip('"').strip()


def gold_key(gold: dict) -> str:
    """Comparison key for a gold answer: numeric value when the answer is a single number,
    otherwise canonical text. Used to detect conflicting golds inside a duplicate cluster."""
    for k in ("value", "answer", "concept", "definition"):
        if k in gold and gold[k] is not None:
            v = parse_number(gold[k])
            if v is not None and str(gold[k]).strip().endswith("%"):
                v /= 100                     # "2.8%" and 0.028 are the same answer
            return f"num:{v:.6g}" if v is not None else "txt:" + text_key(gold[k])
    if "concepts" in gold:
        return "set:" + "|".join(sorted(c.lower() for c in gold["concepts"]))
    if "facts" in gold:
        return "facts:" + "|".join(sorted(f"{text_key(f['fact'])}/{f['type']}" for f in gold["facts"]))
    raise KeyError(f"no comparable gold field in {sorted(gold)}")
