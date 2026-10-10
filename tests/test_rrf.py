"""Spec for rrf(). Pure function: no database, no embeddings."""

import pytest

from night_sky_digest.search import rrf


def test_single_list_keeps_its_order() -> None:
    assert [a for a, _ in rrf([["a", "b", "c"]])] == ["a", "b", "c"]


def test_score_is_one_over_k_plus_rank() -> None:
    scores = dict(rrf([["a", "b"]], k=60))
    assert scores["a"] == pytest.approx(1 / 61)
    assert scores["b"] == pytest.approx(1 / 62)


def test_scores_add_up_across_lists() -> None:
    scores = dict(rrf([["a", "b"], ["b", "a"]], k=60))
    assert scores["a"] == pytest.approx(1 / 61 + 1 / 62)
    assert scores["b"] == pytest.approx(1 / 62 + 1 / 61)


def test_found_by_both_beats_top_of_one() -> None:
    # "both" is 2nd in each list; "lex" and "sem" are each 1st in one list only.
    fused = [a for a, _ in rrf([["lex", "both"], ["sem", "both"]])]
    assert fused[0] == "both"


def test_ids_only_in_one_list_are_kept() -> None:
    assert {a for a, _ in rrf([["a"], ["b"]])} == {"a", "b"}


def test_ties_are_broken_by_id() -> None:
    assert [a for a, _ in rrf([["b"], ["a"]])] == ["a", "b"]


def test_k_trades_one_top_rank_against_broad_agreement() -> None:
    # x is 1st in one list only; y is 4th in both.
    lists = [["x", "f0", "f1", "y"], ["f2", "f3", "f4", "y"]]
    small, large = dict(rrf(lists, k=1)), dict(rrf(lists, k=60))
    assert small["x"] > small["y"]  # k=1: 1/2 vs 2/5, a single top hit wins
    assert large["y"] > large["x"]  # k=60: 1/61 vs 2/64, agreement wins


def test_empty_input() -> None:
    assert rrf([]) == [] and rrf([[]]) == []
