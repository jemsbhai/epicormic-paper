"""Exact binomial tools against reference values."""

from __future__ import annotations

import math

import pytest

from epicormic_lab.stats import (
    binomial_cdf,
    binomial_pmf,
    binomial_sf,
    clopper_pearson,
    ecdf_at,
    holm,
    ks_uniform,
)


def test_binomial_edge_cases() -> None:
    assert binomial_pmf(-1, 5, 0.5) == 0.0
    assert binomial_pmf(6, 5, 0.5) == 0.0
    assert binomial_pmf(0, 5, 0.0) == 1.0
    assert binomial_pmf(1, 5, 0.0) == 0.0
    assert binomial_pmf(5, 5, 1.0) == 1.0
    assert binomial_pmf(4, 5, 1.0) == 0.0
    assert binomial_pmf(2, 4, 0.5) == pytest.approx(0.375)
    assert binomial_cdf(-1, 5, 0.5) == 0.0
    assert binomial_cdf(5, 5, 0.5) == 1.0
    assert binomial_cdf(2, 4, 0.5) == pytest.approx(0.6875)
    assert binomial_sf(0, 5, 0.5) == 1.0
    assert binomial_sf(6, 5, 0.5) == 0.0
    assert binomial_sf(16, 200, 0.05) == pytest.approx(0.0444, abs=5e-4)
    assert binomial_sf(20, 200, 0.05) == pytest.approx(0.00266, abs=5e-5)


def test_clopper_pearson_reference_values() -> None:
    low, high = clopper_pearson(10, 200)
    assert low == pytest.approx(0.02423, abs=1e-4)
    assert high == pytest.approx(0.09003, abs=1e-4)
    low, high = clopper_pearson(0, 200)
    assert low == 0.0
    assert high == pytest.approx(0.01828, abs=1e-4)
    low, high = clopper_pearson(200, 200)
    assert high == 1.0
    assert low == pytest.approx(1 - 0.01828, abs=1e-4)
    with pytest.raises(ValueError, match="k <= n"):
        clopper_pearson(3, 2)
    with pytest.raises(ValueError, match="confidence"):
        clopper_pearson(1, 2, confidence=1.0)


def test_holm_reference() -> None:
    assert holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert holm([]) == []
    assert holm([0.9, 0.8]) == [1.0, 1.0]
    assert holm([0.2, 0.01]) == pytest.approx([0.2, 0.02])


def test_ecdf_and_ks() -> None:
    assert ecdf_at([0.2, 0.4, 0.6, 0.8], (0.5,)) == {"0.5": 0.5}
    assert math.isnan(ecdf_at([], (0.5,))["0.5"])
    assert math.isnan(ks_uniform([]))
    assert ks_uniform([0.5]) == pytest.approx(0.5)
    assert ks_uniform([0.25, 0.5, 0.75]) == pytest.approx(0.25)
    assert ks_uniform([0.0, 0.0]) == pytest.approx(1.0)
