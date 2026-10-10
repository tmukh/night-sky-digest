"""Ranking metrics for one query. Averages over queries happen in the caller."""


def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    """Share of the relevant papers that appear in the top k.

    TODO(M3, Tarik): implement. Spec in tests/test_metrics.py.
    Raise ValueError if `relevant` is empty (recall is undefined; the caller skips that query).
    """
    raise NotImplementedError


def reciprocal_rank(ranked: list[str], relevant: set[str]) -> float:
    """1 / (1-based position of the first relevant paper), or 0.0 if none is in the list.
    The mean over all queries is MRR.

    TODO(M3, Tarik): implement.
    """
    raise NotImplementedError


def ndcg_at_k(ranked: list[str], grades: dict[str, int], k: int) -> float:
    """Normalised discounted cumulative gain over the top k, for graded relevance (0/1/2).

    DCG@k = sum over positions i = 1..k of (2**grade - 1) / log2(i + 1); papers missing from
    `grades` count as grade 0. nDCG@k = DCG@k of `ranked` / DCG@k of the ideal ranking (all graded
    papers sorted by grade, best first). Raise ValueError if no paper has a grade above 0.

    TODO(M3, Tarik): implement.
    """
    raise NotImplementedError
