"""The seed salt, the mock provider specification, the drift kinds and the mixture."""

from __future__ import annotations

import pytest
from epicormic import AnalysisConfig, Monitor, Panel, Probe, analyze, observe
from pollard import MemoryStore

from epicormic_lab.providers import (
    DRIFT_KINDS,
    LENGTH_DELTA,
    REPLICATION_STRIDE,
    SWAPPED_TOOL,
    WINDOW_STRIDE,
    ProviderError,
    drift_level,
    drifted_provider,
    mixture,
    mock_provider,
    salted,
    window_salt,
)

SPEC = {"kind": "epicormic.mock.MockProvider", "seed": 7, "match_rate": "0.9", "drift": None}


def test_window_salt_values_and_bounds() -> None:
    assert window_salt(0, 0) == 0
    assert window_salt(0, 1) == WINDOW_STRIDE
    assert window_salt(3, 2) == 3 * REPLICATION_STRIDE + 2 * WINDOW_STRIDE
    with pytest.raises(ProviderError, match="non-negative"):
        window_salt(-1, 0)
    with pytest.raises(ProviderError, match="overlap"):
        window_salt(0, REPLICATION_STRIDE // WINDOW_STRIDE)


def test_salted_offsets_the_seed_and_requires_one() -> None:
    seen: list[dict[str, object]] = []

    def fn(request: dict[str, object]) -> dict[str, object]:
        seen.append(request)
        return {"text": "ok"}

    step = salted(fn, replication=2, window_index=1)
    assert step({"input": "q", "seed": 5}) == {"text": "ok"}
    assert seen[0]["seed"] == 5 + 2 * REPLICATION_STRIDE + WINDOW_STRIDE
    with pytest.raises(ProviderError, match="seed_from_attempt"):
        step({"input": "q"})


def test_mock_provider_spec_validation() -> None:
    provider = mock_provider(SPEC)
    assert provider.seed == 7 and provider.match_rate == 0.9
    for bad, message in (
        ({**SPEC, "kind": "other"}, "kind"),
        ({**SPEC, "drift": {"match_rate": 0.4}}, "drift null"),
        ({**SPEC, "seed": True}, "integer"),
        ({**SPEC, "seed": "7"}, "integer"),
        ({**SPEC, "match_rate": "abc"}, "decimal"),
        ({**SPEC, "match_rate": "1.5"}, "\\[0, 1\\]"),
    ):
        with pytest.raises(ProviderError, match=message):
            mock_provider(bad)


def _panel() -> Panel:
    return Panel(
        name="aa",
        probes=tuple(Probe(f"q{i}", {"input": f"question {i}"}) for i in range(8)),
        sampling={"temperature": "0.7"},
        seed_from_attempt=True,
    )


def _pooled_t(store: MemoryStore, panel: Panel, config: AnalysisConfig) -> dict[str, str]:
    verdict = analyze(store, Monitor("m", panel.digest, ("w0",), config), "w1")
    return {name: block["pooled"]["T"] for name, block in verdict.payload["scorers"].items()}


def test_unsalted_windows_are_identical_and_salted_windows_are_not() -> None:
    panel = _panel()
    config = AnalysisConfig(scorers=("normalized_match", "output_chars"), permutations=200)
    store = MemoryStore()
    provider = mock_provider(SPEC)
    observe(panel, window_id="w0", samples=5, fn=provider, store=store)
    observe(panel, window_id="w1", samples=5, fn=provider, store=store)
    assert set(_pooled_t(store, panel, config).values()) == {"0"}
    store = MemoryStore()
    provider = mock_provider(SPEC)
    observe(panel, window_id="w0", samples=5, fn=salted(provider, 0, 0), store=store)
    observe(panel, window_id="w1", samples=5, fn=salted(provider, 0, 1), store=store)
    assert set(_pooled_t(store, panel, config).values()) != {"0"}


def _requests(probes: int = 8, attempts: int = 5) -> list[dict[str, object]]:
    """Requests as a panel with ``seed_from_attempt`` issues them: one seed per attempt."""

    return [
        {"input": f"question {probe}", "seed": attempt}
        for attempt in range(attempts)
        for probe in range(probes)
    ]


def test_mixture_routes_by_the_whole_request_and_validates_the_fraction() -> None:
    def base(request: dict[str, object]) -> dict[str, object]:
        return {"text": "base"}

    def drifted(request: dict[str, object]) -> dict[str, object]:
        return {"text": "drifted"}

    assert all(mixture(base, drifted, 0.0)(r)["text"] == "base" for r in _requests())
    assert all(mixture(base, drifted, 1.0)(r)["text"] == "drifted" for r in _requests())
    half = mixture(base, drifted, 0.5)
    routed = [half(r)["text"] for r in _requests()]
    assert routed == [half(r)["text"] for r in _requests()]
    assert 0 < routed.count("drifted") < len(routed)
    # the probes of one attempt share a seed and still part ways
    by_attempt = [set(routed[a * 8 : (a + 1) * 8]) for a in range(5)]
    assert any(len(parts) == 2 for parts in by_attempt)
    with pytest.raises(ProviderError, match="fraction"):
        mixture(base, drifted, 1.5)


def test_drift_level_parses_decimal_strings_in_the_unit_interval() -> None:
    assert drift_level("0.2") == 0.2
    assert drift_level(1) == 1.0
    for bad in ("0", "1.5", "-0.1", "abc"):
        with pytest.raises(ProviderError, match="drift level"):
            drift_level(bad)


def test_drifted_provider_realises_each_kind_at_its_extreme() -> None:
    requests = _requests()
    null = mock_provider(SPEC)
    everything_variant = drifted_provider(SPEC, "match", "0.9")
    assert all("variant" in everything_variant(r)["text"] for r in requests)
    refused = drifted_provider(SPEC, "refusal", "1")
    assert all(refused(r)["finish_reason"] == "content_filter" for r in requests)
    truncated = drifted_provider(SPEC, "truncation", "1")
    assert all(truncated(r)["finish_reason"] == "length" for r in requests)
    swapped = drifted_provider(SPEC, "tool_swap", "1")
    assert all(swapped(r)["tool_calls"][0]["name"] == SWAPPED_TOOL for r in requests)
    padded = drifted_provider(SPEC, "length", "1")
    assert all(padded(r)["text"].endswith("x" * LENGTH_DELTA) for r in requests)
    # a partial mixture leaves the rest of the requests exactly as the null answers them
    some = drifted_provider(SPEC, "tool_swap", "0.3")
    outputs = [some(r) for r in requests]
    kept = [o for o in outputs if o["tool_calls"][0]["name"] != SWAPPED_TOOL]
    pairs = zip(outputs, requests, strict=True)
    assert kept and all(o["text"] == null(r)["text"] for o, r in pairs)
    assert set(DRIFT_KINDS) == {"match", "refusal", "truncation", "tool_swap", "length"}


def test_drifted_provider_keeps_the_null_seed_and_rejects_bad_arguments() -> None:
    requests = _requests(probes=40, attempts=5)
    null = mock_provider(SPEC)
    lowered = drifted_provider(SPEC, "match", "0.3")
    null_variants = {i for i, r in enumerate(requests) if "variant" in null(r)["text"]}
    drift_variants = {i for i, r in enumerate(requests) if "variant" in lowered(r)["text"]}
    assert null_variants and null_variants <= drift_variants and drift_variants > null_variants
    with pytest.raises(ProviderError, match="exceeds the null match rate"):
        drifted_provider(SPEC, "match", "0.95")
    with pytest.raises(ProviderError, match="drift kind"):
        drifted_provider(SPEC, "latency", "0.5")
    with pytest.raises(ProviderError, match="drift level"):
        drifted_provider(SPEC, "match", "0")
