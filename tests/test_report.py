"""Phase 10: the report's figures come from generated files, not from typing."""
import json
import re

from fineval.fetch import ROOT

REPORT = ROOT / "report"


def _prose():
    src = (REPORT / "main.tex").read_text(encoding="utf-8")
    body = src[src.index(r"\begin{document}"):]
    body = re.sub(r"(?<!\\)%.*", "", body)                                    # comments
    body = re.sub(r"\\(cite|ref|label|tabinput|input|bibliography|bibliographystyle|texttt|begin|end)"
                  r"(\[[^\]]*\])?\{[^}]*\}", "", body)
    body = re.sub(r"\$[^$]*\$", "", body)                                      # math
    body = re.sub(r"\\vspace\{[^}]*\}|\[leftmargin=[^\]]*\]", "", body)          # layout lengths
    for name in ("v1", "SHA-256", "BM25", "F1"):                               # names, not figures
        body = body.replace(name, "")
    return body


def test_no_typed_digits_in_report_prose():
    offenders = [line.strip() for line in _prose().splitlines() if re.search(r"\d", line)]
    assert offenders == []


def test_every_macro_used_is_generated():
    macros = json.loads((REPORT / "numbers.json").read_text(encoding="utf-8"))
    src = (REPORT / "main.tex").read_text(encoding="utf-8")
    used = set(re.findall(r"\\((?:n|ret)[A-Z][A-Za-z]*)", src))
    assert used and used <= set(macros)


def test_every_table_input_exists():
    src = (REPORT / "main.tex").read_text(encoding="utf-8")
    for t in re.findall(r"\\tabinput\{([^}]*)\}", src):
        assert (REPORT / t).exists(), t
