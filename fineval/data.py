"""Read the built benchmark (data/v1) and pick leakage-safe few-shot examples."""
import json
import random
from functools import lru_cache

from .build import OUT


@lru_cache(maxsize=None)
def items(task: str, split: str = "test") -> tuple:
    p = OUT / split / f"{task}.jsonl"
    if not p.exists():
        return ()
    return tuple(json.loads(l) for l in p.open(encoding="utf-8"))


def sample(task: str, n: int | None, seed: int = 0, split: str = "test", primary_only: bool = False) -> list:
    """Fixed, seeded subset stratified by source subset. n=None returns everything."""
    rows = [r for r in items(task, split) if r["primary"] or not primary_only]
    if n is None or n >= len(rows):
        return list(rows)
    groups = {}
    for r in rows:
        groups.setdefault(r["subset"], []).append(r)
    rng = random.Random(seed)
    out = []
    for name in sorted(groups):
        g = sorted(groups[name], key=lambda r: r["uid"])
        k = round(n * len(g) / len(rows))
        out += rng.sample(g, min(k, len(g)))
    return sorted(out, key=lambda r: r["uid"])


def fewshot_pool(task: str, test_item: dict, k: int, seed: int = 0) -> list:
    """Examples from validation, then train, never from the test item's own filing or cluster."""
    pool = [r for sp in ("validation", "train") for r in items(task, sp)
            if r["cluster_id"] != test_item["cluster_id"]
            and not (test_item.get("filing_key") and r.get("filing_key") == test_item["filing_key"])]
    rng = random.Random(f"{seed}:{test_item['uid']}")
    return rng.sample(pool, min(k, len(pool)))
