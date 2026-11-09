import json, re, sys
import pandas as pd
EXT, REPO = sys.argv[1], sys.argv[2]
T = REPO + "/external/Regulations_Challenge_COLING_2025/"
def k(s): return re.sub(r"\s+", " ", re.sub(r"^\d+\.\s*", "", str(s)).strip().strip('"')).lower()
for f in ["xa_term", "xa_fb", "xa_formula"]:
    x = pd.read_excel(f"{EXT}/{f}.xlsx", sheet_name=None)
    for sh, df in x.items(): print(f, sh, df.shape, list(df.columns)[:8])
# XBRL terminology
xt = pd.read_excel(f"{EXT}/xa_term.xlsx"); ct = pd.concat([pd.read_csv(T+"testing/Task7-XBRL/Task7-XBRL Terminology-testing.csv"), pd.read_csv(T+"validation/Task7-XBRL/Task7-XBRL Terminology-validation.csv")])
a = set(map(k, xt.iloc[:, 0])); b = set(map(k, ct["Term"]))
print("XBRL terms: XBRL-Agent", len(a), "COLING test+val", len(b), "overlap", len(a & b))
# FinanceBench
fb = [json.loads(l) for l in open(f"{EXT}/fb_open.jsonl", encoding="utf-8")]
fbid = {r["financebench_id"] for r in fb}
cd = pd.concat([pd.read_csv(T+"testing/Task7-XBRL/Task7-XBRL-domain_numberic_query-testing.csv"), pd.read_csv(T+"validation/Task7-XBRL/Task7-XBRL-domain_numberic_query-validation.csv")]).dropna(subset=["question"])
cid = set(cd["financebench_id"].dropna())
xf = pd.read_excel(f"{EXT}/xa_fb.xlsx"); xid = set(xf["financebench_id"].dropna()) if "financebench_id" in xf else set()
print("FinanceBench open 150 | COLING domain/numeric ids", len(cid), "overlap w FB-open", len(cid & fbid), "| XBRL-Agent fb ids", len(xid), "overlap XA and FB", len(xid & fbid), "XA and COLING", len(xid & cid))
# formulas
xm = pd.read_excel(f"{EXT}/xa_formula.xlsx"); cm = pd.read_csv(T+"testing/Task7-XBRL/Task7-XBRL-financial_math-testing.tsv", sep="\t")
print("formulas: XA formula names", xm.iloc[:, 0].nunique(), "COLING test formula names", cm["Formula Name"].nunique(), "overlap", len(set(map(k, xm.iloc[:, 0])) & set(map(k, cm["Formula Name"]))))
xq = set(); [xq.update(map(k, xm[c].dropna())) for c in xm.columns if "uestion" in str(c)]
print("  formula questions XA", len(xq), "overlap with COLING test questions", len(xq & set(map(k, cm["Question"]))))
# EMIR RAG vs COLING
ea = pd.read_csv(f"{EXT}/emir_abbr.csv"); ca = pd.read_csv(T+"testing/Task1-Abbreviation/Task1-Abbreviation-testing.csv")
print("EMIR-RAG abbr", ea.shape, list(ea.columns)[:4], "overlap with COLING abbr test", len(set(map(k, ea.iloc[:, 1 if ea.shape[1] > 2 else 0])) & set(map(k, ca["abbreviations"]))))
el = pd.read_csv(f"{EXT}/esma_link.csv"); cl = pd.read_csv(T+"testing/Task5-Law_Link/Task5-Law_Link-testing.csv")
print("ESMA links", el.shape, list(el.columns)[:3], "overlap with COLING link test", len(set(map(k, el.iloc[:, 0])) & set(map(k, cl["Laws"]))))
