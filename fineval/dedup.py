"""Duplicate detection across all sources (Phase 3).

Items are compared only within the same task. Two items are joined automatically only when
  1. they carry the same strong source id (FinanceBench id), or
  2. their normalised text is identical (exact hash).
Near-identical pairs are never joined automatically. Every cross-source copy we know of is exact
after normalisation, while near matches are mostly distinct items: XBRL elements that differ by
one word ("Due from" vs "Due to", "Current" vs "Noncurrent") or templated questions about another
company. A pair goes to the human review file when it comes from two different datasets/splits,
contains exactly the same numbers, has similarity >= REVIEW_LOW, and neither item already has an
exact copy in the other's dataset. It is joined only if the reviewer writes "join".
"""
import csv
import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from datasketch import MinHash, MinHashLSH
from rapidfuzz import fuzz

from .normalize import exact_hash, gold_key, numbers_in, text_key

REVIEW_LOW = 0.85
LSH_THRESHOLD = 0.5
NUM_PERM = 128

# The original publisher of an item wins when choosing a cluster's representative.
SOURCE_PRIORITY = {"financebench": 0, "xbrl_agent": 1, "fintagging": 1, "coling": 2}
SPLIT_PRIORITY = {"test": 0, "validation": 1, "train": 2}


def match_text(rec) -> str:
    """The field that defines an item's identity for its task."""
    i = rec["input"]
    if rec["task"] == "terminology":
        return i["term"]
    if rec["task"] == "fact_extraction":
        return i["context"]
    return i.get("question") or i["query"]


def strong_id(rec):
    return rec["source_id"] if rec["task"] == "filing_qa" and str(rec["source_id"]).startswith("financebench_id_") else None


def similarity(a: str, b: str) -> float:
    return fuzz.ratio(a, b) / 100.0


def dataset_of(rec) -> tuple:
    return rec["source"], rec["subset"], rec["source_split"]


def _shingles(key: str):
    words = key.split()
    if len(words) >= 8:
        return {" ".join(words[i:i + 3]) for i in range(len(words) - 2)}
    return {key[i:i + 4] for i in range(max(1, len(key) - 3))}


class UnionFind:
    def __init__(self, items):
        self.parent = {x: x for x in items}

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


@dataclass
class DedupResult:
    cluster_of: dict                       # uid -> cluster_id
    clusters: dict                         # cluster_id -> {"task", "representative", "members", "joined_by"}
    conflicts: list                        # clusters whose members' golds disagree
    review: list                           # near-duplicate pairs awaiting / carrying a human decision
    joins: list = field(default_factory=list)   # every pairwise join with its reason


def load_decisions(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as f:
        return {(r["uid_a"], r["uid_b"]): r["decision"].strip().lower()
                for r in csv.DictReader(f) if r.get("decision", "").strip()}


def representative(members):
    return min(members, key=lambda r: (SOURCE_PRIORITY[r["source"]], SPLIT_PRIORITY[r["source_split"]], r["uid"]))


def dedup(records: list, decisions: dict | None = None) -> DedupResult:
    decisions = decisions or {}
    by_uid = {r["uid"]: r for r in records}
    uf = UnionFind(sorted(by_uid))
    joins, review = [], []

    def join(a, b, reason, score=None):
        a, b = sorted((a, b))
        joins.append({"uid_a": a, "uid_b": b, "reason": reason, "score": score})
        uf.union(a, b)

    by_task = defaultdict(list)
    for r in records:
        by_task[r["task"]].append(r)

    for task, recs in sorted(by_task.items()):
        recs = sorted(recs, key=lambda r: r["uid"])
        keys = {r["uid"]: text_key(match_text(r)) for r in recs}
        nums = {r["uid"]: numbers_in(match_text(r)) for r in recs}

        # 1. strong ids
        first = {}
        for r in recs:
            sid = strong_id(r)
            if sid:
                if sid in first:
                    join(first[sid], r["uid"], "same_source_id")
                else:
                    first[sid] = r["uid"]

        # 2. exact normalised text
        first = {}
        for r in recs:
            h = exact_hash(match_text(r))
            if h in first:
                join(first[h], r["uid"], "exact_text")
            else:
                first[h] = r["uid"]

        # 3. near duplicates -> review queue: MinHash LSH proposes candidates, edit similarity filters
        exact_partner = defaultdict(set)      # uid -> datasets holding an exact/id copy of it
        cluster_sets = defaultdict(set)
        for r in recs:
            cluster_sets[uf.find(r["uid"])].add(dataset_of(r))
        for r in recs:
            exact_partner[r["uid"]] = cluster_sets[uf.find(r["uid"])]
        lsh = MinHashLSH(threshold=LSH_THRESHOLD, num_perm=NUM_PERM)
        mh = {}
        for r in recs:
            m = MinHash(num_perm=NUM_PERM, seed=1)
            for s in _shingles(keys[r["uid"]]):
                m.update(s.encode("utf-8"))
            mh[r["uid"]] = m
            lsh.insert(r["uid"], m)
        seen = set()
        for u in sorted(mh):
            for v in sorted(lsh.query(mh[u])):
                if v == u or (min(u, v), max(u, v)) in seen:
                    continue
                a, b = min(u, v), max(u, v)
                seen.add((a, b))
                if uf.find(a) == uf.find(b) or keys[a] == keys[b]:
                    continue
                da, db = dataset_of(by_uid[a]), dataset_of(by_uid[b])
                if nums[a] != nums[b] or da == db:
                    continue
                if db in exact_partner[a] or da in exact_partner[b]:
                    continue
                s = round(similarity(keys[a], keys[b]), 4)
                if s >= REVIEW_LOW:
                    d = decisions.get((a, b), "")
                    review.append({"task": task, "uid_a": a, "uid_b": b, "score": s, "decision": d,
                                   "text_a": match_text(by_uid[a])[:300], "text_b": match_text(by_uid[b])[:300]})
                    if d == "join":
                        join(a, b, "human_review", s)

    groups = defaultdict(list)
    for uid in by_uid:
        groups[uf.find(uid)].append(by_uid[uid])

    reasons = defaultdict(set)
    for j in joins:
        reasons[uf.find(j["uid_a"])].add(j["reason"])

    clusters, cluster_of, conflicts = {}, {}, []
    for root, members in groups.items():
        rep = representative(members)
        cid = "c" + hashlib.sha1(rep["uid"].encode("utf-8")).hexdigest()[:12]
        members = sorted(members, key=lambda r: r["uid"])
        clusters[cid] = {"task": rep["task"], "representative": rep["uid"],
                         "members": [m["uid"] for m in members], "joined_by": sorted(reasons[root])}
        for m in members:
            cluster_of[m["uid"]] = cid
        if len(members) > 1:
            gk = defaultdict(list)
            for m in members:
                gk[gold_key(m["gold"])].append(m["uid"])
            if len(gk) > 1:
                conflicts.append({"cluster_id": cid, "task": rep["task"], "representative": rep["uid"],
                                  "kind": "same_input_different_gold" if len({text_key(match_text(m)) for m in members}) == 1
                                          else "near_input_different_gold",
                                  "golds": {k: v for k, v in sorted(gk.items())}})
    return DedupResult(cluster_of, clusters, sorted(conflicts, key=lambda c: c["cluster_id"]),
                       sorted(review, key=lambda r: (r["task"], r["uid_a"], r["uid_b"])), joins)
