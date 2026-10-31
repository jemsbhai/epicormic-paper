"""Pre-registered paired H-C2 analysis; the full EXP-C runner follows separately.

The unit of inference is a replication pair, not a window or an individual
cell. The endpoint is a restricted delay: 15 means no alarm in 14 observed
windows, not an observed alarm at window 15. Pre-change alarms are separate
from censoring and exclude both members of the pair. No symmetry of paired
differences or exchangeability of the quiet-length labels is assumed.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Mapping, Sequence
from typing import Any

from epicormic_lab.stats import clopper_pearson, holm

H_C2_LEVELS = ("0.3", "0.5")
H_C2_QUIET_WINDOWS = (0, 28)
H_C2_HORIZON = 14
H_C2_MINIMUM_PENALTY = 3
H_C2_ALPHA = 0.05


def _index_chains(
    chains: Sequence[dict[str, Any]], level: str, quiet: int, replications: int
) -> dict[int, dict[str, Any]]:
    indexed: dict[int, dict[str, Any]] = {}
    for chain in chains:
        rep = chain["replication"]
        if type(rep) is not int or rep < 0 or rep in indexed:
            raise ValueError("H-C2 needs unique non-negative integer replication ids")
        if chain["kind"] != "match" or chain["level"] != level:
            raise ValueError("H-C2 chain kind or level differs from its cell")
        change = quiet + 1
        if chain["change_window"] != change or chain["windows"] != quiet + H_C2_HORIZON:
            raise ValueError(
                "H-C2 needs the registered quiet length and complete 14-window horizon"
            )
        alarm = chain["detectors"]["normalized_match"]["eprocess"]
        first, delay, before = alarm["first"], alarm["delay"], alarm["pre_change"]
        if type(before) is not bool:
            raise ValueError("pre_change must be a boolean")
        if first is not None and (type(first) is not int or not 1 <= first <= chain["windows"]):
            raise ValueError("first alarm is outside the recorded chain")
        expected_before = first is not None and first < change
        expected_delay = None if first is None or expected_before else first - change + 1
        if before != expected_before or delay != expected_delay:
            raise ValueError("inconsistent e-process first alarm, pre-change flag, or delay")
        if delay is not None and type(delay) is not int:
            raise ValueError("delay must be an integer or null")
        indexed[rep] = alarm
    if set(indexed) != set(range(replications)):
        raise ValueError("H-C2 needs every planned replication in both cells; no silent inner join")
    return indexed


def paired_delay_penalty(
    short: Sequence[dict[str, Any]],
    long: Sequence[dict[str, Any]],
    *,
    level: str,
    replications: int,
) -> dict[str, Any]:
    """Exact paired threshold test for one level, from ``first_alarms`` summaries.

    Summaries also carry ``replication``, ``kind``, and ``level``. Both cells
    must contain exactly the planned ids, including censored and pre-alarm
    chains. Test H0: P(Y28 - Y0 >= 3 | both pre-alarm-free) <= 1/2 against
    greater than 1/2, using the exact binomial upper tail. All eligible pairs
    remain in the denominator; a difference exactly 3 is a success, and zero
    or negative differences are failures. Across-level Holm is applied by
    ``summarize_h_c2``. This function alone makes no confirmatory decision.
    """

    if level not in H_C2_LEVELS or type(replications) is not int or replications <= 0:
        raise ValueError("H-C2 needs a registered level and positive replication count")
    left = _index_chains(short, level, 0, replications)
    right = _index_chains(long, level, 28, replications)
    pairs: list[dict[str, Any]] = []
    excluded: list[int] = []
    for rep in range(replications):
        a, b = left[rep], right[rep]
        if a["pre_change"] or b["pre_change"]:
            excluded.append(rep)
            continue
        a_censored, b_censored = a["delay"] is None, b["delay"] is None
        y0 = H_C2_HORIZON + 1 if a_censored else a["delay"]
        y28 = H_C2_HORIZON + 1 if b_censored else b["delay"]
        pairs.append(
            {
                "replication": rep,
                "restricted_delay_0": y0,
                "restricted_delay_28": y28,
                "censored_0": a_censored,
                "censored_28": b_censored,
                "difference": y28 - y0,
            }
        )
    differences = [pair["difference"] for pair in pairs]
    successes = sum(d >= H_C2_MINIMUM_PENALTY for d in differences)
    total = len(pairs)
    return {
        "level": level,
        "planned_pairs": replications,
        "eligible_pairs": total,
        "excluded_pre_change_replications": excluded,
        "pre_change_alarms_0": sum(a["pre_change"] for a in left.values()),
        "pre_change_alarms_28": sum(b["pre_change"] for b in right.values()),
        "pairs": pairs,
        "pairs_at_least_3": successes,
        "fraction_at_least_3": successes / total if total else None,
        "fraction_ci95": list(clopper_pearson(successes, total)) if total else None,
        "median_paired_restricted_difference": statistics.median(differences) if total else None,
        # p0=1/2 permits integer arithmetic until the final division.
        # With no eligible pairs this is choose(0, 0) / 1 = 1.
        "raw_p": sum(math.comb(total, j) for j in range(successes, total + 1)) / 2**total,
    }


def summarize_h_c2(
    cells: Mapping[str, Mapping[int, Sequence[dict[str, Any]]]], *, replications: int
) -> dict[str, Any]:
    """Apply the fixed two-level Holm family, retaining p=1 for no eligible pairs.

    ``cells[level][quiet_windows]`` contains that cell's chain summaries.
    The caller must verify the frozen protocol, run provenance, and full
    profile before treating this numerical summary as confirmatory evidence.
    """

    if set(cells) != set(H_C2_LEVELS) or any(
        set(cells[level]) != set(H_C2_QUIET_WINDOWS) for level in cells
    ):
        raise ValueError("H-C2 needs both registered levels and quiet lengths 0 and 28")
    levels = [
        paired_delay_penalty(
            cells[level][0], cells[level][28], level=level, replications=replications
        )
        for level in H_C2_LEVELS
    ]
    adjusted = holm([result["raw_p"] for result in levels])
    for result, p in zip(levels, adjusted, strict=True):
        result["holm_p"] = p
        result["criterion_met"] = bool(result["eligible_pairs"] and p <= H_C2_ALPHA)
    return {
        "test": "exact_paired_threshold_binomial",
        "horizon_windows": H_C2_HORIZON,
        "minimum_penalty_windows": H_C2_MINIMUM_PENALTY,
        "family_alpha": H_C2_ALPHA,
        "levels": levels,
        "criterion_met_both_levels": all(result["criterion_met"] for result in levels),
    }
