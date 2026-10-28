"""Step callables for the experiments: the seeded mock, and the per-window seed salt.

Two windows of one panel on one deterministic provider receive identical
seeds, because ``seed_base`` is part of the panel digest and the window
header copies it. Under the null that makes the windows identical and every
pooled statistic exactly zero (measured with epicormic 0.1.0 on 2026-10-28).
The salt below lives in the step callable, outside the pollard identity
payload and outside the panel digest, and makes the seed sets of different
windows disjoint. The EXP-A pre-registration, section 3.2, states the formula.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from typing import Any

from epicormic import MockProvider

StepFn = Callable[[dict[str, Any]], dict[str, Any]]

REPLICATION_STRIDE = 100_000
WINDOW_STRIDE = 1_000
MOCK_KIND = "epicormic.mock.MockProvider"


class ProviderError(ValueError):
    """A provider specification or a request is not what the protocol requires."""


def window_salt(replication: int, window_index: int) -> int:
    """The seed offset of window ``window_index`` of replication ``replication``.

    Window index 0 is the baseline window and 1..K are the current windows.
    The strides keep seed sets disjoint while N is below 1000 and a
    replication has fewer than 100 windows.
    """

    if replication < 0 or window_index < 0:
        raise ProviderError("replication and window_index must be non-negative")
    if window_index >= REPLICATION_STRIDE // WINDOW_STRIDE:
        raise ProviderError(f"window_index {window_index} would overlap the next replication")
    return REPLICATION_STRIDE * replication + WINDOW_STRIDE * window_index


def salted(fn: StepFn, replication: int, window_index: int, seed_field: str = "seed") -> StepFn:
    """Wrap ``fn`` so that every request's seed is offset by the window salt."""

    salt = window_salt(replication, window_index)

    def step(request: dict[str, Any]) -> dict[str, Any]:
        if seed_field not in request:
            raise ProviderError(
                f"request has no {seed_field!r}; the panel must set seed_from_attempt"
            )
        salted_request = dict(request)
        salted_request[seed_field] = int(request[seed_field]) + salt
        return fn(salted_request)

    return step


def mock_provider(spec: dict[str, Any]) -> MockProvider:
    """Build the null mock provider that a protocol's ``provider`` block describes."""

    if spec.get("kind") != MOCK_KIND:
        raise ProviderError(f"provider kind must be {MOCK_KIND!r}, got {spec.get('kind')!r}")
    if spec.get("drift") is not None:
        raise ProviderError("the calibration provider must declare drift null")
    seed = spec.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ProviderError("provider seed must be an integer")
    try:
        match_rate = float(Decimal(str(spec.get("match_rate", "0.9"))))
    except InvalidOperation as error:
        raise ProviderError("provider match_rate must be a decimal string") from error
    if not 0.0 <= match_rate <= 1.0:
        raise ProviderError("provider match_rate must lie in [0, 1]")
    return MockProvider(seed=seed, match_rate=match_rate)
