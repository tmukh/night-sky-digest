"""Spec for the ranking metrics. Expected values are written as the formula, so you can check
them by hand."""

from math import log2

import pytest

from night_sky_digest.evals.metrics import ndcg_at_k, recall_at_k, reciprocal_rank

RANKED = ["a", "b", "c", "d"]


def test_recall_counts_relevant_in_top_k() -> None:
    relevant = {"b", "d", "x"}  # x was never retrieved
    assert recall_at_k(RANKED, relevant, k=2) == pytest.approx(1 / 3)
    assert recall_at_k(RANKED, relevant, k=4) == pytest.approx(2 / 3)


def test_recall_k_larger_than_list() -> None:
    assert recall_at_k(["a"], {"a"}, k=10) == pytest.approx(1.0)


def test_recall_undefined_without_relevant() -> None:
    with pytest.raises(ValueError):
        recall_at_k(RANKED, set(), k=10)


def test_reciprocal_rank() -> None:
    assert reciprocal_rank(RANKED, {"c", "d"}) == pytest.approx(1 / 3)
    assert reciprocal_rank(RANKED, {"a"}) == pytest.approx(1.0)
    assert reciprocal_rank(RANKED, {"x"}) == 0.0


def test_ndcg_perfect_ranking_is_one() -> None:
    grades = {"a": 2, "b": 2, "c": 1}
    assert ndcg_at_k(["a", "b", "c"], grades, k=3) == pytest.approx(1.0)


def test_ndcg_known_value() -> None:
    grades = {"a": 2, "b": 1, "c": 0, "d": 2}
    dcg = (2**1 - 1) / log2(2) + (2**2 - 1) / log2(3) + 0  # ranked: b, a, c
    ideal = (2**2 - 1) / log2(2) + (2**2 - 1) / log2(3) + (2**1 - 1) / log2(4)  # a, d, b
    assert ndcg_at_k(["b", "a", "c"], grades, k=3) == pytest.approx(dcg / ideal)


def test_ndcg_unjudged_papers_count_as_zero() -> None:
    grades = {"a": 2}
    assert ndcg_at_k(["x", "a"], grades, k=2) == pytest.approx((3 / log2(3)) / 3)


def test_ndcg_only_top_k_counts() -> None:
    grades = {"a": 2}
    assert ndcg_at_k(["x", "y", "a"], grades, k=2) == 0.0


def test_ndcg_undefined_without_relevant() -> None:
    with pytest.raises(ValueError):
        ndcg_at_k(RANKED, {"a": 0}, k=3)
