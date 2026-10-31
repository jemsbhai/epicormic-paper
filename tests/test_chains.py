"""Change-point chains: observation, ordered analysis, and the first-alarm reduction."""

from __future__ import annotations

from typing import Any

import pytest
from epicormic import AnalysisConfig, Monitor, Panel, Probe, load_panel
from pollard import MemoryStore

from epicormic_lab import chains
from epicormic_lab.chains import (
    DETECTORS,
    ChainError,
    analyze_chain,
    chain_window_ids,
    first_alarms,
    observe_chain,
)
from epicormic_lab.providers import drifted_provider, mock_provider

from .conftest import REPO

SPEC = {"kind": "epicormic.mock.MockProvider", "seed": 7, "match_rate": "0.9", "drift": None}
SCORERS = ("normalized_match", "refusal", "output_chars")


def _panel() -> Panel:
    return load_panel(REPO / "data" / "panels" / "mock-08-v1.json")


def test_chain_window_ids() -> None:
    assert chain_window_ids("C1-r003", 2) == ["C1-r003-w00", "C1-r003-w01", "C1-r003-w02"]


def test_c3_shares_baselines_by_replication_but_uses_absolute_post_change_salts() -> None:
    # Record actual salted requests and mock outputs through observe_chain,
    # rather than restating the salt formula in a unit test.
    panel = _panel()

    def capture(quiet: int, rep: int) -> list[list[tuple[dict[str, Any], dict[str, Any]]]]:
        windows: list[list[tuple[dict[str, Any], dict[str, Any]]]] = []
        providers = []
        for index in range(quiet + 15):
            records: list[tuple[dict[str, Any], dict[str, Any]]] = []
            windows.append(records)
            provider = (
                mock_provider(SPEC) if index <= quiet else drifted_provider(SPEC, "match", "0.3")
            )

            def step(request: dict[str, Any], fn=provider, seen=records) -> dict[str, Any]:
                response = fn(request)
                seen.append((dict(request), response))
                return response

            providers.append(step)
        observe_chain(
            MemoryStore(), panel, samples=2, window_ids=chain_window_ids(f"q{quiet}", quiet + 14),
            providers=providers, replication=rep,
        )
        return windows

    q0, q7, q28, next_rep = capture(0, 0), capture(7, 0), capture(28, 0), capture(0, 1)
    assert q0[0] == q7[0] == q28[0]
    assert q7[:8] == q28[:8]
    assert q0[0] != next_rep[0]
    # Equal absolute index means equal requests, even if the providers differ.
    assert [r for r, _ in q0[1]] == [r for r, _ in q28[1]]
    # Equal post-change offset is NOT a matched post-change stream.
    assert [r for r, _ in q0[1]] != [r for r, _ in q28[29]]
    seeds = {r["seed"] for window in q28 for r, _ in window}
    assert seeds.isdisjoint({r["seed"] for window in next_rep for r, _ in window})


def test_observe_and_analyze_a_chain_with_a_change_at_window_two() -> None:
    panel = _panel()
    config = AnalysisConfig(scorers=SCORERS, permutations=200)
    store = MemoryStore()
    null = mock_provider(SPEC)
    refusing = drifted_provider(SPEC, "refusal", "1")
    ids = chain_window_ids("t-r000", 3)
    recorded = observe_chain(
        store,
        panel,
        samples=10,
        window_ids=ids,
        providers=[null, null, refusing, refusing],
        replication=0,
    )
    assert recorded == 4 * 8 * 10
    monitor = Monitor("t-r000", panel.digest, (ids[0],), config)
    records = analyze_chain(store, monitor, ids[1:], recompute=True)
    assert [r["window_index"] for r in records] == [1, 2, 3]
    assert [r["sequence_index"] for r in records] == [1, 2, 3]
    summary = first_alarms(records, change_window=2, scorers=SCORERS)
    refusal = summary["detectors"]["refusal"]
    # every answer is refused from window 2 on: the pooled test rejects there
    # and the e-process alarms within the first drifted window or the next
    assert refusal["pooled"] == {"first": 2, "pre_change": False, "delay": 1}
    assert refusal["eprocess"]["pre_change"] is False and refusal["eprocess"]["delay"] in (1, 2)
    assert summary["effects"]["refusal"]["T_post_mean"] == pytest.approx(1.0)
    assert summary["effects"]["refusal"]["T_pre_mean"] == 0.0
    assert summary["effects"]["refusal"]["e_before_change"] is not None
    assert summary["state"]["first_drift"] == 2 and summary["state"]["drift_delay"] == 1
    assert summary["state"]["pre_change_drift"] is False
    assert str(summary["state"]["first_drift_rule"]).startswith("pooled test rejected for")
    assert summary["state"]["states"][0] in ("stable", "warning")
    assert set(summary["detectors"]["normalized_match"]) == set(DETECTORS)


def test_observe_chain_refuses_mismatched_or_short_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    panel = _panel()
    null = mock_provider(SPEC)
    with pytest.raises(ChainError, match="providers"):
        observe_chain(
            MemoryStore(), panel, samples=5, window_ids=["a", "b"], providers=[null], replication=0
        )

    class Short:
        recorded = 1
        refused = 0

    monkeypatch.setattr(chains, "observe", lambda *a, **k: Short())
    with pytest.raises(ChainError, match="recorded 1 of 40"):
        observe_chain(
            MemoryStore(), panel, samples=5, window_ids=["a"], providers=[null], replication=0
        )


def test_analyze_chain_reports_a_recompute_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    panel = Panel(
        name="tiny",
        probes=tuple(Probe(f"q{i}", {"input": f"question {i}"}) for i in range(8)),
        sampling={"temperature": "0.7"},
        seed_from_attempt=True,
    )
    config = AnalysisConfig(scorers=("normalized_match",), permutations=100)
    store = MemoryStore()
    null = mock_provider(SPEC)
    ids = chain_window_ids("m", 1)
    observe_chain(store, panel, samples=5, window_ids=ids, providers=[null, null], replication=1)
    monitor = Monitor("m", panel.digest, (ids[0],), config)
    real = chains.recompute_verdict
    monkeypatch.setattr(chains, "recompute_verdict", lambda *a, **k: (real(*a, **k)[0], False))
    with pytest.raises(ChainError, match="recomputed verdict differs"):
        analyze_chain(store, monitor, ids[1:], recompute=True)


def _record(index: int, state: str, **flags: Any) -> dict[str, Any]:
    return {
        "window_index": index,
        "state": state,
        "rule_fired": f"rule at {index}",
        "pooled": {"s": {"T": flags.get("T", 0.1), "rejected": flags.get("rejected", False)}},
        "sequential": {
            "s": {
                "e_alarm": flags.get("e", False),
                "cusum_alarm": flags.get("cusum", False),
                "ph_alarm": flags.get("ph"),
                "e": flags.get("e_value", 1.0),
            }
        },
    }


def test_first_alarms_handles_pre_change_alarms_and_censoring() -> None:
    records = [
        _record(1, "stable", rejected=True, T=None),
        _record(2, "drift", e=True),
        _record(3, "stable"),
        _record(4, "stable", rejected=True, cusum=True, T=0.3),
    ]
    summary = first_alarms(records, change_window=3, scorers=("s",))
    s = summary["detectors"]["s"]
    # a sticky detector that alarmed before the change has no delay
    assert s["eprocess"] == {"first": 2, "pre_change": True, "delay": None}
    # the pooled test is window by window: a rejection before the change is
    # a pre-change false alarm and the first rejection after it is the delay
    assert s["pooled"] == {"first": 4, "pre_change": True, "delay": 2}
    assert s["cusum"] == {"first": 4, "pre_change": False, "delay": 2}
    assert s["page_hinkley"] == {"first": None, "pre_change": False, "delay": None}
    assert summary["effects"]["s"]["T_pre_mean"] == pytest.approx(0.1)
    assert summary["effects"]["s"]["T_post_mean"] == pytest.approx(0.2)
    assert summary["effects"]["s"]["e_before_change"] == 1.0
    state = summary["state"]
    assert state["first_drift"] == 2 and state["pre_change_drift"] is True
    assert state["drift_delay"] is None and state["first_drift_rule"] == "rule at 2"
    assert state["first_warning_or_drift"] == 2
    quiet = first_alarms([_record(1, "stable", T=None)], change_window=1, scorers=("s",))
    assert quiet["effects"]["s"] == {
        "T_pre_mean": None,
        "T_post_mean": None,
        "e_before_change": None,
        "e_last": 1.0,
    }
    assert quiet["state"]["first_drift"] is None and quiet["state"]["first_drift_rule"] is None
    with pytest.raises(ChainError, match="outside"):
        first_alarms(records, change_window=5, scorers=("s",))
