"""Exact binomial tools for the calibration analyses, in pure Python.

The analysis of EXP-A needs one-sided exact binomial p-values, two-sided
Clopper-Pearson intervals, the Holm adjustment, and uniformity diagnostics
for p-values. None of these needs more than the binomial distribution, so
they are implemented here against ``math.lgamma`` and a bisection, and the
test suite checks them against reference values.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def _log_choose(n: int, k: int) -> float:
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def binomial_pmf(k: int, n: int, p: float) -> float:
    """P(X = k) for X ~ Binomial(n, p)."""

    if k < 0 or k > n:
        return 0.0
    if p <= 0.0:
        return 1.0 if k == 0 else 0.0
    if p >= 1.0:
        return 1.0 if k == n else 0.0
    return math.exp(_log_choose(n, k) + k * math.log(p) + (n - k) * math.log1p(-p))


def binomial_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k)."""

    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    return min(1.0, sum(binomial_pmf(i, n, p) for i in range(k + 1)))


def binomial_sf(k: int, n: int, p: float) -> float:
    """P(X >= k), the one-sided exact p-value of observing at least ``k`` successes."""

    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    return min(1.0, sum(binomial_pmf(i, n, p) for i in range(k, n + 1)))


def _solve(target: float, n: int, k: int, upper: bool) -> float:
    """Find p with binomial_cdf(k, n, p) = target (upper) or binomial_sf(k, n, p) = target."""

    # binomial_cdf(k, n, p) falls as p rises, binomial_sf(k, n, p) rises with p; the
    # bisection moves the bound that leaves the target on the far side.
    low, high = 0.0, 1.0
    for _ in range(80):
        mid = (low + high) / 2
        value = binomial_cdf(k, n, mid) if upper else binomial_sf(k, n, mid)
        if (value > target) == upper:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def clopper_pearson(k: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Two-sided exact binomial confidence interval for a proportion ``k`` of ``n``."""

    if n <= 0 or k < 0 or k > n:
        raise ValueError("need 0 <= k <= n with n positive")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must lie strictly between 0 and 1")
    tail = (1.0 - confidence) / 2
    lower = 0.0 if k == 0 else _solve(tail, n, k, upper=False)
    higher = 1.0 if k == n else _solve(tail, n, k, upper=True)
    return lower, higher


def holm(pvalues: Sequence[float]) -> list[float]:
    """Holm step-down adjusted p-values, in the input order."""

    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, (m - rank) * pvalues[index])
        adjusted[index] = min(1.0, running)
    return adjusted


def ecdf_at(values: Sequence[float], points: Sequence[float]) -> dict[str, float]:
    """The empirical fraction of ``values`` at or below each point, keyed by the point."""

    n = len(values)
    if n == 0:
        return {str(point): math.nan for point in points}
    ordered = sorted(values)
    return {str(point): sum(1 for v in ordered if v <= point) / n for point in points}


def ks_uniform(values: Sequence[float]) -> float:
    """Kolmogorov-Smirnov distance between the empirical distribution and Uniform(0, 1)."""

    n = len(values)
    if n == 0:
        return math.nan
    ordered = sorted(values)
    distance = 0.0
    for index, value in enumerate(ordered):
        distance = max(distance, (index + 1) / n - value, value - index / n)
    return distance
