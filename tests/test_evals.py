from pathlib import Path

import pytest

from night_sky_digest.evals.agreement import cohen_kappa, confusion
from night_sky_digest.evals.queries import load_queries


def test_queries_file_is_valid() -> None:
    queries = load_queries(Path(__file__).parent.parent / "eval" / "queries.yaml")
    assert len(queries) >= 60
    assert {q.subfield for q in queries} == {"CO", "EP", "GA", "HE", "IM", "SR"}


def test_kappa_perfect_agreement() -> None:
    assert cohen_kappa([0, 1, 2, 2], [0, 1, 2, 2]) == pytest.approx(1.0)


def test_kappa_chance_level() -> None:
    # Judge b's grades are independent of a's: agreement equals what chance predicts.
    a = [0, 0, 1, 1]
    b = [0, 1, 0, 1]
    assert cohen_kappa(a, b) == pytest.approx(0.0)


def test_kappa_known_value() -> None:
    # 2x2 textbook case: p_o = 0.7, p_e = 0.5 -> kappa = 0.4
    a = [1] * 5 + [0] * 5
    b = [1, 1, 1, 0, 0, 0, 0, 0, 0, 1]  # 3 + 4 agreements; b has 4 ones, 6 zeros
    assert cohen_kappa(a, b) == pytest.approx(0.4)


def test_linear_weights_forgive_near_misses() -> None:
    a = [0, 1, 2, 0, 1, 2]
    near = [1, 1, 2, 0, 2, 2]  # off by one twice
    far = [2, 1, 2, 0, 0, 2]  # off by two once, by one once
    assert cohen_kappa(a, near, "linear") > cohen_kappa(a, near)
    assert cohen_kappa(a, near, "linear") > cohen_kappa(a, far, "linear")


def test_confusion_counts() -> None:
    m = confusion([0, 1, 2], [0, 2, 2])
    assert m[(0, 0)] == 1 and m[(1, 2)] == 1 and m[(2, 2)] == 1 and m[(2, 0)] == 0
