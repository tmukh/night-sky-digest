"""Ranking metrics for one query. Averages over queries happen in the caller."""

from math import log2


def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    """Share of the relevant papers that appear in the top k.

    Spec in tests/test_metrics.py.
    Raise ValueError if `relevant` is empty (recall is undefined; the caller skips that query).
    """
    if not relevant:
        raise ValueError("recall is undefined without relevant papers")
    return len(set(ranked[:k]) & relevant) / len(relevant)


def reciprocal_rank(ranked: list[str], relevant: set[str]) -> float:
    """1 / (1-based position of the first relevant paper), or 0.0 if none is in the list.
    The mean over all queries is MRR.
    """
    for position, arxiv_id in enumerate(ranked, start=1):
        if arxiv_id in relevant:
            return 1.0 / position
    return 0.0


def ndcg_at_k(ranked: list[str], grades: dict[str, int], k: int) -> float:
    """Normalised discounted cumulative gain over the top k, for graded relevance (0/1/2).

    DCG@k = sum over positions i = 1..k of (2**grade - 1) / log2(i + 1); papers missing from
    `grades` count as grade 0. nDCG@k = DCG@k of `ranked` / DCG@k of the ideal ranking (all graded
    papers sorted by grade, best first). Raise ValueError if no paper has a grade above 0.
    """
    ideal = _dcg(sorted(grades.values(), reverse=True)[:k])
    if ideal == 0:
        raise ValueError("nDCG is undefined without relevant papers")
    return _dcg([grades.get(arxiv_id, 0) for arxiv_id in ranked[:k]]) / ideal


def _dcg(gains: list[int]) -> float:
    # Position i (1-based) is discounted by log2(i + 1): rank 1 counts fully, rank 3 half.
    return sum((2**g - 1) / log2(i + 1) for i, g in enumerate(gains, start=1))
