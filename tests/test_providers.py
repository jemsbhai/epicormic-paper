"""The seed salt and the mock provider specification."""

from __future__ import annotations

import pytest
from epicormic import AnalysisConfig, Monitor, Panel, Probe, analyze, observe
from pollard import MemoryStore

from epicormic_lab.providers import (
    REPLICATION_STRIDE,
    WINDOW_STRIDE,
    ProviderError,
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
