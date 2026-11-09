"""Every external source FinEval reads, pinned to an exact commit or revision.

A file is identified by (source, path). `fetch.py` downloads it to data/raw/<source>/<path>
and records its SHA-256 in data/raw/MANIFEST.json; loaders refuse files that don't match.
"""

GH_RAW = "https://raw.githubusercontent.com/{repo}/{commit}/{path}"

SOURCES = {
    "xbrl_agent": {
        "title": "XBRL-Agent (Han et al., ICAIF 2024)",
        "repo": "KirkHan0920/XBRL-Agent",
        "commit": "eafd6154f055058fcabcebc16868a0f877721def",
        "licence": "MIT",
        "files": [
            "Datasets/XBRL Terminology.xlsx",
            "Datasets/formulas_with_explanations_with_questions_with_gt.xlsx",
            "Datasets/financebench.xlsx",
        ],
    },
    "financebench": {
        "title": "FinanceBench (Islam et al., 2023), open-source sample",
        "repo": "patronus-ai/financebench",
        "commit": "cc39aeb4afdf33909ee1412188bf89035950c2eb",
        "licence": "CC-BY-NC-4.0",
        "files": [
            "data/financebench_open_source.jsonl",
            "data/financebench_document_information.jsonl",
        ],
    },
    "fintagging": {
        "title": "FinTagging (Wang et al., 2025), GitHub release",
        "repo": "The-FinAI/FinTagging",
        "commit": "ff426bc4c914c3cc6d967a696fbc041ed157c459",
        "licence": "MIT (code), CC-BY-4.0 (data)",
        "files": [
            "subdata/FinCL-eval-subset.csv",
            "subdata/FinNI-eval-subset.csv",
            "taxonomy/us-gaap-2024.xsd",
            "taxonomy/us_gaap_2024_BM25.jsonl",
            "annotation/TrainingSet_Annotation.json",
            "annotation/benchmark_ground_truth_pipeline.json",
            "retrieval/retrieval.py",
            "README.md",
        ],
    },
    "coling": {
        "title": "Regulations Challenge, COLING 2025 (Wang et al., 2025)",
        "repo": "Open-Finance-Lab/Regulations_Challenge_COLING_2025",
        "commit": "01cfe520903ca2977b3af9b7fe9d3a1f16879045",
        "licence": "CDLA-Permissive-2.0",
        "files": [
            "testing/Task7-XBRL/Task7-XBRL Terminology-testing.csv",
            "validation/Task7-XBRL/Task7-XBRL Terminology-validation.csv",
            "testing/Task7-XBRL/Task7-XBRL-domain_numberic_query-testing.csv",
            "validation/Task7-XBRL/Task7-XBRL-domain_numberic_query-validation.csv",
            "testing/Task7-XBRL/Task7-XBRL-financial_math-testing.tsv",
            "validation/Task7-XBRL/Task7-XBRL-financial_math-validation.csv",
            "testing/Task7-XBRL/Task7-XBRL-Tag_Query_to_XBRL_Reports-testing.csv",
            "validation/Task7-XBRL/Task7-XBRL-Tag_Query_to_XBRL_Reports-validation.csv",
        ],
    },
}

# Papers whose tables reference/published.json cites. Saved to data/raw/papers/<name>.pdf, with a
# text extract next to it for tests/test_published.py. Versioned arXiv URLs never change.
PAPERS = {
    "fintagging_2505.20650v5": "https://arxiv.org/pdf/2505.20650v5",
    "financebench_2311.11944v1": "https://arxiv.org/pdf/2311.11944v1",
    "coling_report_2412.11159v2": "https://arxiv.org/pdf/2412.11159v2",
}

# Full FinTagging / FinAuditing sets on Hugging Face are gated: access needs a form the
# account owner fills in. Recorded here so the datasheet lists them; not fetched by default.
GATED_HF = {
    "TheFinAI/en-fincl-eval-v2": "8519075e25bacb3fcd1563ca6b5ebd1699ba428b",
    "TheFinAI/en-finni-eval-v2": "5e18f6472ebeaf525b644ca8e87ab7bc03bf543a",
    "TheFinAI/en-fintagging-original-v2": "a658d70e41e2ccb022f95ebf61e598cbc3d7b963",
    "TheFinAI/en-finsm": None,
    "TheFinAI/en-finred": None,
    "TheFinAI/en-finmr": None,
}


def url(source: str, path: str) -> str:
    s = SOURCES[source]
    from urllib.parse import quote
    return GH_RAW.format(repo=s["repo"], commit=s["commit"], path=quote(path))
