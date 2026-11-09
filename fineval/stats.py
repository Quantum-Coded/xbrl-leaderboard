"""Bootstrap confidence intervals and paired comparisons (resampling items, fixed seeds)."""
import random


def bootstrap_ci(xs, n=2000, seed=0, alpha=0.05, stat=None):
    """CI of `stat` (default mean) over items. `xs` may be numbers or per-item dicts if `stat`
    takes a list of them (e.g. pooled F1)."""
    stat = stat or (lambda v: sum(v) / len(v))
    if not xs:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    k = len(xs)
    sims = sorted(stat([xs[rng.randrange(k)] for _ in range(k)]) for _ in range(n))
    return sims[int(alpha / 2 * n)], sims[int((1 - alpha / 2) * n) - 1]


def paired_bootstrap(a, b, n=2000, seed=0, alpha=0.05, stat=None):
    """Difference stat(b) - stat(a) on the same items, with CI and the share of resamples where
    b does not beat a (a one-sided p-value proxy)."""
    assert len(a) == len(b)
    stat = stat or (lambda v: sum(v) / len(v))
    rng = random.Random(seed)
    k = len(a)
    diffs = []
    for _ in range(n):
        idx = [rng.randrange(k) for _ in range(k)]
        diffs.append(stat([b[i] for i in idx]) - stat([a[i] for i in idx]))
    diffs.sort()
    return {"diff": stat(b) - stat(a), "ci": (diffs[int(alpha / 2 * n)], diffs[int((1 - alpha / 2) * n) - 1]),
            "p_not_better": sum(d <= 0 for d in diffs) / n}


def noise_groups(scores: dict) -> list:
    """Group models whose CIs overlap the leader's, top-down: [[best, ...], [next, ...], ...].
    `scores` maps model -> (value, (lo, hi))."""
    order = sorted(scores, key=lambda m: -scores[m][0])
    groups = []
    while order:
        lead = order[0]
        lo = scores[lead][1][0]
        g = [m for m in order if scores[m][1][1] >= lo]
        groups.append(g)
        order = [m for m in order if m not in g]
    return groups
