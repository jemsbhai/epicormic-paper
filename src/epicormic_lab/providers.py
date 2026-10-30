"""Step callables for the experiments: the seeded mock, the per-window seed salt, and drift.

Two windows of one panel on one deterministic provider receive identical
seeds, because ``seed_base`` is part of the panel digest and the window
header copies it. Under the null that makes the windows identical and every
pooled statistic exactly zero (measured with epicormic 0.1.0 on 2026-10-28).
The salt below lives in the step callable, outside the pollard identity
payload and outside the panel digest, and makes the seed sets of different
windows disjoint. The EXP-A pre-registration, section 3.2, states the formula.

The drift kinds are the post-change providers of EXP-C (and later EXP-B).
Three of the mock's drifts are rates and grade on their own; the tool swap
and the length padding apply to every answer, so they are graded through a
mixture that routes a fraction of the requests to the drifted mock. The
EXP-C pre-registration, section 3.1, states the constructions and the
realised effect of each on the Cliff's delta scale.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from typing import Any

from epicormic import Drift, MockProvider

StepFn = Callable[[dict[str, Any]], dict[str, Any]]

REPLICATION_STRIDE = 100_000
WINDOW_STRIDE = 1_000
MOCK_KIND = "epicormic.mock.MockProvider"
MIXTURE_TAG = b"epicormic-lab/mixture/v1:"
SWAPPED_TOOL = "search"
LENGTH_DELTA = 20
# drift kind -> the scorer that measures it directly (its primary scorer)
DRIFT_KINDS: dict[str, str] = {
    "match": "normalized_match",
    "refusal": "refusal",
    "truncation": "truncated",
    "tool_swap": "tool_call_set_jaccard",
    "length": "output_chars",
}


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


def mixture(base: StepFn, drifted: StepFn, fraction: float) -> StepFn:
    """Route each request to ``drifted`` with probability ``fraction``, else to ``base``.

    The decision is a hash of the whole request, content and seed, so it is
    a pure function of the request: the same request is routed the same way
    in every process and on every rerun, and the requests of one window are
    routed independently of each other. Hashing the seed alone would route
    the same attempt of every probe together, because the panel gives every
    probe the seed ``seed_base + attempt``.
    """

    if not 0.0 <= fraction <= 1.0:
        raise ProviderError(f"mixture fraction must lie in [0, 1], got {fraction}")

    def step(request: dict[str, Any]) -> dict[str, Any]:
        material = json.dumps(request, sort_keys=True, default=repr).encode("utf-8")
        digest = hashlib.sha256(MIXTURE_TAG + material).digest()
        unit = int.from_bytes(digest[:8], "big") / 2**64
        return drifted(request) if unit < fraction else base(request)

    return step


def drift_level(level: Any) -> float:
    """Parse a nominal drift level, a decimal string in (0, 1]."""

    try:
        value = float(Decimal(str(level)))
    except InvalidOperation as error:
        raise ProviderError(f"drift level must be a decimal string, got {level!r}") from error
    if not 0.0 < value <= 1.0:
        raise ProviderError(f"drift level must lie in (0, 1], got {level!r}")
    return value


def drifted_provider(spec: dict[str, Any], kind: str, level: Any) -> StepFn:
    """The post-change step callable of drift ``kind`` at nominal ``level``.

    ``spec`` is the protocol's ``provider`` block, which describes the null
    mock; the drifted mock keeps its seed, so an answer that is a variant
    under the null is a variant under the drift (common random numbers).
    ``match`` lowers the match rate by ``level``; ``refusal`` and
    ``truncation`` set that rate to ``level``; ``tool_swap`` and ``length``
    send a fraction ``level`` of the requests to a mock that renames the
    tool to ``search`` or pads every answer by 20 characters.
    """

    base = mock_provider(spec)
    value = drift_level(level)
    if kind == "match":
        if value > base.match_rate:
            raise ProviderError(
                f"match level {level!r} exceeds the null match rate {base.match_rate}"
            )
        drift = Drift(match_rate=base.match_rate - value)
        return MockProvider(seed=base.seed, match_rate=base.match_rate, drift=drift)
    if kind == "refusal":
        return MockProvider(
            seed=base.seed, match_rate=base.match_rate, drift=Drift(refusal_rate=value)
        )
    if kind == "truncation":
        return MockProvider(
            seed=base.seed, match_rate=base.match_rate, drift=Drift(truncation_rate=value)
        )
    if kind == "tool_swap":
        swapped = MockProvider(
            seed=base.seed, match_rate=base.match_rate, drift=Drift(swap_tool=SWAPPED_TOOL)
        )
        return mixture(base, swapped, value)
    if kind == "length":
        padded = MockProvider(
            seed=base.seed, match_rate=base.match_rate, drift=Drift(length_delta=LENGTH_DELTA)
        )
        return mixture(base, padded, value)
    raise ProviderError(f"drift kind must be one of {tuple(DRIFT_KINDS)}, got {kind!r}")
