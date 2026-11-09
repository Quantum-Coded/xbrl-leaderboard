"""Group-aware split assignment and leakage control (Phase 4).

Each duplicate cluster gets exactly one FinEval split:
  test       if any member is in a source's test/eval set,
  validation if not, but any member is in a validation set,
  train      otherwise.
So a test item can never reappear in validation or train under another source's name.

Training items are additionally dropped when
  * their cluster has conflicting golds (we can't tell which label is right), or
  * they sit in a near-duplicate review pair with a non-train item that a human hasn't
    marked "separate" (possible leak), or
  * their text contains a test item's text verbatim (a test context embedded in a longer one).

For test clusters the gold is chosen as follows:
  * one member only, or all golds agree: the representative's gold.
  * members from different sources disagree: the original publisher's gold (the representative)
    is kept and the item is flagged `source_disagreement`. It stays in the primary score.
  * members from the same dataset share an identical input but carry different golds: no single
    answer is defensible, so the item is flagged `ambiguous`, its gold becomes the union of the
    members' golds, and it is excluded from the primary score (reported as a sensitivity row).
"""
from collections import defaultdict

from .dedup import dataset_of, match_text
from .normalize import text_key

SPLIT_ORDER = ("test", "validation", "train")


def assign(records: list, res) -> dict:
    by_uid = {r["uid"]: r for r in records}
    conflict_of = {c["cluster_id"]: c for c in res.conflicts}

    split_of_cluster = {}
    for cid, c in res.clusters.items():
        splits = {by_uid[u]["source_split"] for u in c["members"]}
        split_of_cluster[cid] = next(s for s in SPLIT_ORDER if s in splits)

    # near-duplicate pairs that may still be the same item
    risky = defaultdict(set)
    for p in res.review:
        if p["decision"] != "separate":
            risky[p["uid_a"]].add(p["uid_b"])
            risky[p["uid_b"]].add(p["uid_a"])

    test_keys = defaultdict(list)          # task -> normalised texts of test items, for containment
    for cid, c in res.clusters.items():
        if split_of_cluster[cid] == "test":
            rep = by_uid[c["representative"]]
            test_keys[rep["task"]].append(text_key(match_text(rep)))

    items, dropped = [], []
    for cid, c in sorted(res.clusters.items()):
        split = split_of_cluster[cid]
        rep = by_uid[c["representative"]]
        members = [by_uid[u] for u in c["members"]]
        flags, gold = [], rep["gold"]
        conf = conflict_of.get(cid)
        if conf:
            same_dataset = len({dataset_of(m) for m in members}) == 1
            if same_dataset or conf["kind"] == "same_input_different_gold" and _one_dataset_disagrees(conf, by_uid):
                flags.append("ambiguous")
                gold = _union_gold(members)
            else:
                flags.append("source_disagreement")

        if split == "train":
            reason = None
            if conf:
                reason = "conflicting_gold"
            elif any(by_uid[o]["source_split"] != "train" or split_of_cluster[res.cluster_of[o]] != "train"
                     for u in c["members"] for o in risky[u]):
                reason = "near_duplicate_of_eval_item"
            else:
                k = text_key(match_text(rep))
                if any(t and len(t) >= 40 and t in k for t in test_keys[rep["task"]]):
                    reason = "contains_test_text"
            if reason:
                dropped.append({"cluster_id": cid, "uid": rep["uid"], "reason": reason})
                continue

        items.append({
            "cluster_id": cid, "split": split, "task": rep["task"], "uid": rep["uid"],
            "source": rep["source"], "subset": rep["subset"], "also_in": [u for u in c["members"] if u != rep["uid"]],
            "input": rep["input"], "gold": gold, "metric": rep["metric"], "licence": rep["licence"],
            "filing_key": rep.get("filing_key"), "flags": flags, "primary": "ambiguous" not in flags,
            "provenance": rep["provenance"], "meta": rep.get("meta", {}),
        })

    # Different questions about the same filing are not duplicates, but an example from a test
    # item's filing must never be shown with it. Flag them; fewshot.pool() enforces the rule.
    test_filings = {i["filing_key"] for i in items if i["split"] == "test" and i["filing_key"]}
    for it in items:
        if it["split"] != "test" and it["filing_key"] in test_filings:
            it["flags"].append("filing_in_test")
    return {"items": items, "dropped": dropped}


def _one_dataset_disagrees(conf, by_uid) -> bool:
    """True when two members of the same dataset carry different golds for an identical input."""
    seen = {}
    for gk, uids in conf["golds"].items():
        for u in uids:
            d = dataset_of(by_uid[u])
            if d in seen and seen[d] != gk:
                return True
            seen[d] = gk
    return False


def _union_gold(members) -> dict:
    g = members[0]["gold"]
    if "concepts" in g:
        return {**g, "concepts": sorted({c for m in members for c in m["gold"]["concepts"]})}
    for k in ("definition", "answer", "value"):
        if k in g:
            return {**g, f"{k}_alternatives": sorted({str(m["gold"][k]) for m in members})}
    return g
