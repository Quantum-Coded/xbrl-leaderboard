"""Build the FinEval v1 dataset from the pinned raw sources (Phases 2-4).

    python -I -m fineval.build

Writes data/v1/ (benchmark items per task and split, clusters, conflicts, overlap matrix,
dropped/skipped rows) and review/near_dups.csv. Human decisions already in review/near_dups.csv
are kept and re-applied. Output is deterministic: running twice gives identical files.
"""
import csv
import json
from collections import Counter, defaultdict

from .dedup import dataset_of, dedup, load_decisions
from .fetch import ROOT
from .schema import validate
from .sources.loaders import load_all
from .splits import assign

OUT = ROOT / "data" / "v1"
REVIEW = ROOT / "review" / "near_dups.csv"


def _dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")


def overlap_matrix(records, res) -> dict:
    """For every ordered pair of datasets in the same task: how many items of A have a copy in B."""
    by_uid = {r["uid"]: r for r in records}
    ds_of_cluster = defaultdict(set)
    for r in records:
        ds_of_cluster[res.cluster_of[r["uid"]]].add(":".join(dataset_of(r)))
    size = Counter(":".join(dataset_of(r)) for r in records)
    pairs = Counter()
    for r in records:
        a = ":".join(dataset_of(r))
        for b in ds_of_cluster[res.cluster_of[r["uid"]]]:
            if b != a:
                pairs[(a, b)] += 1
    task_of = {":".join(dataset_of(r)): r["task"] for r in by_uid.values()}
    rows = [{"task": task_of[a], "dataset": a, "size": size[a], "in_dataset": b, "overlap": n,
             "share": round(n / size[a], 4)} for (a, b), n in sorted(pairs.items())]
    return {"datasets": {d: {"task": task_of[d], "size": n} for d, n in sorted(size.items())}, "pairs": rows}


def main():
    loaded = load_all()
    records = [r.to_dict() for r in loaded.records]
    for r in records:
        validate(r)
    if len({r["uid"] for r in records}) != len(records):
        raise SystemExit("duplicate uids")

    res = dedup(records, load_decisions(REVIEW))
    split = assign(records, res)

    # review file: keep any decisions already written, list every current pair
    REVIEW.parent.mkdir(parents=True, exist_ok=True)
    with REVIEW.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, ["task", "uid_a", "uid_b", "score", "decision", "text_a", "text_b"])
        w.writeheader()
        w.writerows(res.review)

    items = split["items"]
    by_task_split = defaultdict(list)
    for it in items:
        by_task_split[(it["task"], it["split"])].append(it)
    for (task, sp), rows in sorted(by_task_split.items()):
        _jsonl(OUT / sp / f"{task}.jsonl", sorted(rows, key=lambda r: r["uid"]))

    _jsonl(OUT / "clusters.jsonl", [{"cluster_id": k, **v} for k, v in sorted(res.clusters.items())])
    _dump(OUT / "conflicts.json", res.conflicts)
    _dump(OUT / "overlap.json", overlap_matrix(records, res))
    _dump(OUT / "dropped.json", split["dropped"])
    _dump(OUT / "skipped.json", loaded.skipped)

    summary = {
        "records_loaded": len(records),
        "rows_skipped": len(loaded.skipped),
        "clusters": len(res.clusters),
        "multi_member_clusters": sum(len(c["members"]) > 1 for c in res.clusters.values()),
        "joins": dict(Counter(j["reason"] for j in res.joins)),
        "conflicts": dict(Counter(f"{c['task']}:{c['kind']}" for c in res.conflicts)),
        "review_pairs": len(res.review),
        "review_pending": sum(1 for p in res.review if not p["decision"]),
        "train_dropped": dict(Counter(d["reason"] for d in split["dropped"])),
        "items": {f"{t}:{s}": len(v) for (t, s), v in sorted(by_task_split.items())},
        "primary_items": {f"{t}:{s}": sum(i["primary"] for i in v) for (t, s), v in sorted(by_task_split.items())},
        "flags": dict(Counter(f"{i['task']}:{f}" for i in items for f in i["flags"])),
    }
    _dump(OUT / "summary.json", summary)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
