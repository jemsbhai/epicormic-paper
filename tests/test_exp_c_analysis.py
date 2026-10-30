"""Paired finite-horizon inference, checked against independent exact references."""

from __future__ import annotations

import json
import math
from copy import deepcopy
from typing import Any

import pytest
from scipy.stats import binomtest

from epicormic_lab.exp_c_analysis import (
    H_C2_ALPHA,
    H_C2_HORIZON,
    H_C2_LEVELS,
    H_C2_MINIMUM_PENALTY,
    H_C2_QUIET_WINDOWS,
    paired_delay_penalty,
    summarize_h_c2,
)
from epicormic_lab.protocol import load_protocol

from .conftest import EXP_C_PROTOCOL


def _chain(
    rep: int, quiet: int, delay: int | None, *, level: str = "0.3", pre: bool = False
) -> dict[str, Any]:
    first = 1 if pre else None if delay is None else quiet + delay
    return {
        "replication": rep,
        "kind": "match",
        "level": level,
        "change_window": quiet + 1,
        "windows": quiet + 14,
        "detectors": {
            "normalized_match": {
                "eprocess": {
                    "first": first,
                    "pre_change": pre,
                    "delay": delay,
                }
            }
        },
    }


def test_pairing_uses_replication_ids_and_keeps_censors_and_ties() -> None:
    short = [_chain(i, 0, d) for i, d in enumerate([1, 12, 14, None, None, 4, 2])]
    long = [_chain(i, 28, d) for i, d in enumerate([4, None, None, None, 1, 1, None])]
    long[6] = _chain(6, 28, None, pre=True)
    out = paired_delay_penalty(short, list(reversed(long)), level="0.3", replications=7)
    assert out["eligible_pairs"] == 6 and out["excluded_pre_change_replications"] == [6]
    assert out["pre_change_alarms_0"] == 0 and out["pre_change_alarms_28"] == 1
    assert [p["difference"] for p in out["pairs"]] == [3, 3, 1, 0, -14, -3]
    assert out["pairs_at_least_3"] == 2
    assert out["median_paired_restricted_difference"] == 0.5
    assert out["raw_p"] == pytest.approx(binomtest(2, 6, 0.5, alternative="greater").pvalue)
    reference = binomtest(2, 6).proportion_ci()
    assert out["fraction_ci95"] == pytest.approx([reference.low, reference.high])
    assert out["pairs"][1]["censored_28"] is True
    assert out["pairs"][3]["censored_0"] is True
    assert out == paired_delay_penalty(list(reversed(short)), long, level="0.3", replications=7)
    json.dumps(out, allow_nan=False)


def test_no_detection_is_not_dropped_and_is_not_evidence_of_a_penalty() -> None:
    for delay in (None, 1, 14):
        out = paired_delay_penalty(
            [_chain(i, 0, delay) for i in range(50)],
            [_chain(i, 28, delay) for i in range(50)],
            level="0.3",
            replications=50,
        )
        assert out["eligible_pairs"] == 50 and out["pairs_at_least_3"] == 0
        assert out["raw_p"] == 1.0 and out["median_paired_restricted_difference"] == 0


@pytest.mark.parametrize("n", [1, 7, 30, 50])
def test_all_success_counts_match_exact_binomial_reference(n: int) -> None:
    short = [_chain(i, 0, 1) for i in range(n)]
    for k in range(n + 1):
        long = [_chain(i, 28, 4 if i < k else 3) for i in range(n)]
        out = paired_delay_penalty(short, long, level="0.3", replications=n)
        exact = sum(math.comb(n, j) for j in range(k, n + 1)) / 2**n
        assert out["raw_p"] == pytest.approx(exact, abs=1e-14)
        assert out["raw_p"] == pytest.approx(binomtest(k, n, 0.5, alternative="greater").pvalue)


def test_holm_uses_both_levels_and_empty_eligibility_cannot_pass() -> None:
    cells = {
        level: {
            0: [_chain(i, 0, 1, level=level) for i in range(6)],
            28: [_chain(i, 28, 4, level=level) for i in range(6)],
        }
        for level in H_C2_LEVELS
    }
    out = summarize_h_c2(cells, replications=6)
    assert out["criterion_met_both_levels"] is True
    assert [r["holm_p"] for r in out["levels"]] == pytest.approx([2 / 64, 2 / 64])
    cells["0.5"][28] = [_chain(i, 28, None, level="0.5", pre=True) for i in range(6)]
    out = summarize_h_c2(cells, replications=6)
    assert out["criterion_met_both_levels"] is False
    assert out["levels"][0]["holm_p"] == pytest.approx(2 / 64)
    empty = out["levels"][1]
    assert empty["eligible_pairs"] == 0 and empty["raw_p"] == 1 and empty["holm_p"] == 1
    assert empty["fraction_ci95"] is None and empty["fraction_at_least_3"] is None
    assert empty["median_paired_restricted_difference"] is None and not empty["criterion_met"]
    json.dumps(out, allow_nan=False)
    # A merely directional increase is not evidence for the fixed 3-window threshold.
    cells["0.5"][28] = [_chain(i, 28, 3, level="0.5") for i in range(6)]
    assert not summarize_h_c2(cells, replications=6)["criterion_met_both_levels"]
    for bad in ({}, {"0.3": cells["0.3"]}, {**cells, "0.5": {0: cells["0.5"][0]}}):
        with pytest.raises(ValueError, match="both registered"):
            summarize_h_c2(bad, replications=6)


def test_incomplete_pairs_and_malformed_outcomes_stop_analysis() -> None:
    short, long = [_chain(0, 0, 1)], [_chain(0, 28, 4)]
    for field, value, message in (
        ("replication", True, "replication ids"),
        ("replication", -1, "replication ids"),
        ("replication", 1, "every planned"),
        ("kind", "length", "kind or level"),
        ("level", "0.5", "kind or level"),
        ("windows", 41, "complete 14-window"),
        ("change_window", 28, "quiet length"),
    ):
        bad = [{**long[0], field: value}]
        with pytest.raises(ValueError, match=message):
            paired_delay_penalty(short, bad, level="0.3", replications=1)
    for bad in ([], long * 2):
        with pytest.raises(ValueError, match="replication"):
            paired_delay_penalty(short, bad, level="0.3", replications=1)
    for field, value, message in (
        ("pre_change", "false", "boolean"),
        ("first", 43, "outside"),
        ("first", True, "outside"),
        ("first", None, "inconsistent"),
        ("pre_change", True, "inconsistent"),
        ("delay", None, "inconsistent"),
        ("delay", 15, "inconsistent"),
        ("delay", 4.0, "integer or null"),
    ):
        bad = deepcopy(long)
        bad[0]["detectors"]["normalized_match"]["eprocess"][field] = value
        with pytest.raises(ValueError, match=message):
            paired_delay_penalty(short, bad, level="0.3", replications=1)
    for level, n in (("0.2", 1), ("0.3", 0), ("0.3", True)):
        with pytest.raises(ValueError, match="registered level"):
            paired_delay_penalty(short, long, level=level, replications=n)


def test_protocol_matches_executable_analysis_and_keeps_original_version() -> None:
    protocol = load_protocol(EXP_C_PROTOCOL)
    h_c2 = next(h for h in protocol.document["outcomes"]["primary"] if h["id"] == "H-C2")
    spec = h_c2["paired_analysis"]
    assert spec["test"] == "exact_paired_threshold_binomial"
    assert spec["pair_key"] == ["level", "replication"]
    assert tuple(spec["levels"]) == H_C2_LEVELS
    assert tuple(spec["quiet_windows"]) == H_C2_QUIET_WINDOWS
    assert spec["horizon_windows"] == H_C2_HORIZON
    assert spec["restricted_no_alarm_value"] == H_C2_HORIZON + 1
    assert spec["minimum_penalty_windows"] == H_C2_MINIMUM_PENALTY
    assert spec["success_comparison"] == ">=" and spec["alternative"] == "greater"
    assert float(spec["null_probability"]) == 0.5
    assert float(spec["family_alpha"]) == H_C2_ALPHA
    assert "Mann-Whitney" not in h_c2["test"]
    old = load_protocol(EXP_C_PROTOCOL.with_name("protocol.2026-10-29.json"))
    assert old.digest == protocol.document["supersedes"]["digest"]
    assert old.version == "2026-10-29"
    for key in ("provider", "analysis", "parts", "panels", "software"):
        assert old.document[key] == protocol.document[key]
