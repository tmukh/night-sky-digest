"""How much two judges agree beyond chance."""

from collections import Counter
from typing import Literal

GRADES = (0, 1, 2)


def cohen_kappa(a: list[int], b: list[int], weights: Literal["none", "linear"] = "none") -> float:
    """Cohen's kappa: 1 = perfect agreement, 0 = no better than chance, < 0 = worse than chance.

    kappa = 1 - observed_disagreement / expected_disagreement, where "expected" is what two judges
    with the same grade frequencies would disagree by picking at random. With linear weights a
    0-vs-2 disagreement costs twice as much as 0-vs-1, which suits ordinal grades.
    """
    if len(a) != len(b) or not a:
        raise ValueError("need two equally long, non-empty lists")
    n = len(a)

    def cost(x: int, y: int) -> float:
        if weights == "linear":
            return abs(x - y) / (len(GRADES) - 1)
        return 0.0 if x == y else 1.0

    observed = sum(cost(x, y) for x, y in zip(a, b, strict=True)) / n
    pa, pb = Counter(a), Counter(b)
    expected = sum(pa[x] * pb[y] * cost(x, y) for x in GRADES for y in GRADES) / (n * n)
    if expected == 0:
        return 1.0  # both judges always gave the same single grade
    return 1.0 - observed / expected


def confusion(a: list[int], b: list[int]) -> dict[tuple[int, int], int]:
    counts = Counter(zip(a, b, strict=True))
    return {(x, y): counts[(x, y)] for x in GRADES for y in GRADES}
