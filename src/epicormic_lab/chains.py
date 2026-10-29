"""Change-point chains: one baseline window, K current windows, a provider switch at a known window.

EXP-C runs chains in which the provider changes at a pre-registered window.
The functions here observe such a chain, analyse its current windows in
order, and reduce the per-window verdict records to the quantities the
experiment reports: for each detector and scorer the first window at which
it alarmed, whether that was before the change, and the delay after it; for
the state machine the first ``drift`` and the first ``warning`` or
``drift``; and the realised effect per scorer, the mean pooled statistic
over the windows after the change. The EXP-C pilot and the EXP-C runner
share this module, so the provider switch the pre-registration describes is
the one the experiment runs.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from typing import Any

from epicormic import Monitor, Panel, analyze, observe, recompute_verdict

from epicormic_lab.exp_a import verdict_record
from epicormic_lab.providers import StepFn, salted

DETECTORS = ("eprocess", "cusum", "page_hinkley", "pooled")
_ALARM_FIELD = {
    "eprocess": "e_alarm",
    "cusum": "cusum_alarm",
    "page_hinkley": "ph_alarm",
}


class ChainError(RuntimeError):
    """A chain did not record or analyse what the protocol requires."""


def chain_window_ids(prefix: str, windows: int) -> list[str]:
    """Window ids ``<prefix>-w00`` (baseline) to ``<prefix>-w<K>`` (last current window)."""

    return [f"{prefix}-w{index:02d}" for index in range(windows + 1)]


def observe_chain(
    store: Any,
    panel: Panel,
    *,
    samples: int,
    window_ids: Sequence[str],
    providers: Sequence[StepFn],
    replication: int,
) -> int:
    """Observe every window of a chain with its own provider and the window salt.

    ``providers[index]`` answers window ``window_ids[index]``; index 0 is the
    baseline window. Returns the number of observations recorded and raises
    ``ChainError`` when a window is short or any request was refused.
    """

    if len(providers) != len(window_ids):
        raise ChainError(f"{len(window_ids)} windows but {len(providers)} providers")
    expected = len(panel.probes) * samples
    recorded = 0
    for index, (wid, provider) in enumerate(zip(window_ids, providers, strict=True)):
        report = observe(
            panel,
            window_id=wid,
            samples=samples,
            fn=salted(provider, replication, index, panel.seed_field),
            store=store,
        )
        if report.recorded != expected or report.refused:
            raise ChainError(
                f"{wid}: recorded {report.recorded} of {expected}, refused {report.refused}"
            )
        recorded += report.recorded
    return recorded


def analyze_chain(
    store: Any,
    monitor: Monitor,
    window_ids: Sequence[str],
    *,
    recompute: bool = False,
) -> list[dict[str, Any]]:
    """Analyse the current windows of a chain in order and return their verdict records.

    ``window_ids`` are the current windows only, in index order; the
    baseline is the monitor's. With ``recompute`` every verdict is
    recomputed from the stored observations and a mismatch raises
    ``ChainError``, as the EXP-A runner does.
    """

    records: list[dict[str, Any]] = []
    for offset, wid in enumerate(window_ids):
        verdict = analyze(store, monitor, wid)
        if recompute:
            assert verdict.node_id is not None
            _, matched = recompute_verdict(store, monitor, verdict.node_id)
            if not matched:
                raise ChainError(f"{wid}: recomputed verdict differs from {verdict.node_id}")
        records.append(verdict_record(verdict.payload, offset + 1, verdict.node_id))
    return records


def _first(flags: Sequence[bool]) -> int | None:
    for index, flag in enumerate(flags, start=1):
        if flag:
            return index
    return None


def _alarm_flags(records: Sequence[dict[str, Any]], scorer: str, detector: str) -> list[bool]:
    if detector == "pooled":
        return [bool(record["pooled"][scorer]["rejected"]) for record in records]
    field = _ALARM_FIELD[detector]
    return [bool(record["sequential"][scorer][field]) for record in records]


def _mean(values: Sequence[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return statistics.fmean(present) if present else None


def first_alarms(
    records: Sequence[dict[str, Any]], change_window: int, scorers: Sequence[str]
) -> dict[str, Any]:
    """Reduce a chain's verdict records to first alarms, delays, and realised effects.

    Window indices are 1-based over the current windows; ``change_window``
    is the first window the drifted provider answered. For a detector and
    scorer, ``first`` is the first window with an alarm or ``None``,
    ``pre_change`` says whether that window precedes the change, and
    ``delay`` is ``first - change_window + 1`` when the first alarm is at or
    after the change (1 means the first drifted window), ``None`` otherwise:
    a chain that alarmed before the change has no delay, because the
    detectors are sticky and the alarm cannot be attributed to the change.
    The pooled test is not sticky; its ``first`` is the first window whose
    pooled test rejected at or after the change, and ``pre_change`` counts
    any rejection before it.
    """

    if not 1 <= change_window <= len(records):
        raise ChainError(f"change_window {change_window} is outside 1..{len(records)}")
    detectors: dict[str, dict[str, dict[str, Any]]] = {}
    effects: dict[str, dict[str, float | None]] = {}
    for scorer in scorers:
        detectors[scorer] = {}
        for detector in DETECTORS:
            flags = _alarm_flags(records, scorer, detector)
            if detector == "pooled":
                before = any(flags[: change_window - 1])
                after = _first(flags[change_window - 1 :])
                first = None if after is None else after + change_window - 1
                detectors[scorer][detector] = {
                    "first": first,
                    "pre_change": before,
                    "delay": after,
                }
            else:
                first = _first(flags)
                before = first is not None and first < change_window
                detectors[scorer][detector] = {
                    "first": first,
                    "pre_change": before,
                    "delay": None if first is None or before else first - change_window + 1,
                }
        series = [record["pooled"][scorer]["T"] for record in records]
        e_series = [record["sequential"][scorer]["e"] for record in records]
        effects[scorer] = {
            "T_pre_mean": _mean(series[: change_window - 1]),
            "T_post_mean": _mean(series[change_window - 1 :]),
            "e_before_change": e_series[change_window - 2] if change_window > 1 else None,
            "e_last": e_series[-1],
        }
    states = [str(record["state"]) for record in records]
    first_drift = _first([state == "drift" for state in states])
    first_warning = _first([state in ("warning", "drift") for state in states])
    pre_change_drift = _first([state == "drift" for state in states[: change_window - 1]])
    first_rule = None if first_drift is None else records[first_drift - 1]["rule_fired"]
    return {
        "change_window": change_window,
        "windows": len(records),
        "detectors": detectors,
        "effects": effects,
        "state": {
            "first_drift": first_drift,
            "first_drift_rule": first_rule,
            "first_warning_or_drift": first_warning,
            "pre_change_drift": pre_change_drift is not None,
            "drift_delay": None
            if first_drift is None or first_drift < change_window
            else first_drift - change_window + 1,
            "states": states,
        },
    }
