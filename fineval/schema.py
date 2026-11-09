"""The unified record every source is converted to, and its JSON-schema check."""
from dataclasses import asdict, dataclass, field

import jsonschema

TASKS = ("concept_tagging", "fact_extraction", "financial_calc", "filing_qa", "terminology")
SPLITS = ("test", "validation", "train")


@dataclass
class Record:
    uid: str                 # "<source>:<subset>:<source_split>:<source_id>", unique across FinEval
    source: str              # key in sources.registry.SOURCES
    subset: str              # dataset inside the source, e.g. "fincl_subset"
    source_id: str           # the source's own id, or the row index when it has none
    source_split: str        # split as published by the source
    task: str
    input: dict              # model-facing fields, verbatim from the source
    gold: dict               # gold answer, verbatim; normalised copies are made in scorers only
    metric: str              # scorer id, e.g. "concept_exact@v1"
    licence: str
    provenance: dict         # {"file", "row", "sha256"}
    filing_key: str | None = None   # filing the item is about, when the source says so
    meta: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


SCHEMA = {
    "type": "object",
    "required": ["uid", "source", "subset", "source_id", "source_split", "task", "input", "gold",
                 "metric", "licence", "provenance"],
    "properties": {
        "uid": {"type": "string", "pattern": r"^[a-z_]+:[a-z0-9_]+:(test|validation|train):.+$"},
        "source": {"type": "string"},
        "subset": {"type": "string"},
        "source_id": {"type": "string", "minLength": 1},
        "source_split": {"enum": list(SPLITS)},
        "task": {"enum": list(TASKS)},
        "input": {"type": "object", "minProperties": 1},
        "gold": {"type": "object", "minProperties": 1},
        "metric": {"type": "string", "pattern": r"^[a-z0-9_]+@v\d+$"},
        "licence": {"type": "string"},
        "provenance": {"type": "object", "required": ["file", "row", "sha256"]},
        "filing_key": {"type": ["string", "null"]},
        "meta": {"type": "object"},
    },
}

_validator = jsonschema.Draft202012Validator(SCHEMA)


def validate(rec: dict):
    errors = sorted(_validator.iter_errors(rec), key=str)
    if errors:
        raise ValueError(f"{rec.get('uid')}: {errors[0].message}")
