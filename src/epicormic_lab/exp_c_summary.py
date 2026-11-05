"""From EXP-C cell summaries to the committed, value-free EXP-C summary.

``summarize_exp_c`` reads the ``cells/*.json.gz`` files of one run directory
and computes what section 5 of the EXP-C pre-registration (protocol version
2026-11-05-r3) lists: the shared-window check; per cell, detector and
scorer the pre-change alarms and the detection fractions, quantiles and
histograms; the state machine's eligibility, delays and rules; H-C1 over
the eligible chains with Holm across its family; H-C2 through
``exp_c_analysis.summarize_h_c2`` with the quiet-length table; S-C1 to
S-C6; the export to EXP-D; and the provenance block that says whether the
run can be confirmatory at all. ``write_summary`` writes the result to
``analysis/generated/``, the only place the paper reads numbers from.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from epicormic.stats.sequential import cusum, page_hinkley

from epicormic_lab.chains import DETECTORS
from epicormic_lab.exp_a import RunError
from epicormic_lab.exp_c import chain_cells, read_cell_summary, summary_path
from epicormic_lab.exp_c_analysis import H_C2_HORIZON, H_C2_LEVELS, summarize_h_c2
from epicormic_lab.protocol import load_protocol
from epicormic_lab.stats import binomial_cdf, clopper_pearson, holm

SUMMARY_FORMAT = "epicormic-lab/exp-c-summary/v1"
WITHIN = (1, 2, 7, 14)
STICKY = ("eprocess", "cusum", "page_hinkley")
H_C1_LEVELS = ("0.2", "0.3", "0.5")
H_C1_WITHIN = 2
H_C1_P0 = 0.90
H_C1_ALPHA = 0.05
H_C1_FAMILY = 15
H_C1_POWER_RATES = (0.80, 0.75)
S_C4_LEVELS = ("0.1", "0.2")
S_C5_LEVEL = "0.2"
S_C5_NULL_WINDOWS = 28
S_C5_UPPER_BOUND = 0.10
CUSUM_GRID = tuple((k, h) for k in (0.05, 0.1, 0.15, 0.2) for h in (0.2, 0.3, 0.4, 0.6, 0.8, 1.0))
PH_GRID = tuple((d, lam) for d in (0.025, 0.05, 0.1) for lam in (0.25, 0.5, 0.75, 1.0))
CUSUM_DEFAULT = (0.1, 0.4)
PH_DEFAULT = (0.05, 0.5)
EXP_D_GEOMETRY = (24, 10, 14)  # panel size, N, quiet windows of the EXP-D operating point
MISMATCH_LIMIT = 50


def _rate(count: int, total: int) -> dict[str, Any]:
    if total == 0:
        return {"count": count, "total": 0, "rate": None, "ci95": None}
    low, high = clopper_pearson(count, total)
    return {"count": count, "total": total, "rate": count / total, "ci95": [low, high]}


def detection_quantile(delays: Sequence[int | None], horizon: int, q: float) -> int | str:
    """The inverse empirical detection CDF quantile of section 5.

    The smallest integer d in 1..horizon whose detected fraction is at least
    ``q``; "above <horizon>" when no d reaches it; "not estimable" without
    chains. Never computed among the alarms alone.
    """

    if not delays:
        return "not estimable"
    for d in range(1, horizon + 1):
        if sum(1 for delay in delays if delay is not None and delay <= d) / len(delays) >= q:
            return d
    return f"above {horizon}"


def detection_block(delays: Sequence[int | None], horizon: int) -> dict[str, Any]:
    """Detection within d windows, the delay quantiles and the first-alarm histogram."""

    total = len(delays)
    return {
        "total": total,
        "censored": sum(1 for delay in delays if delay is None),
        "within": {
            str(d): _rate(sum(1 for delay in delays if delay is not None and delay <= d), total)
            for d in WITHIN
        },
        "median": detection_quantile(delays, horizon, 0.5),
        "p90": detection_quantile(delays, horizon, 0.9),
        "histogram": {
            str(key): count
            for key, count in sorted(Counter(d for d in delays if d is not None).items())
        },
    }


def _spread(values: Sequence[float | None]) -> dict[str, Any]:
    present = [v for v in values if v is not None]
    return {
        "n": len(present),
        "mean": statistics.fmean(present) if present else None,
        "sd": statistics.stdev(present) if len(present) >= 2 else None,
    }


def _range(values: Sequence[float | None]) -> dict[str, Any]:
    present = [v for v in values if v is not None]
    return {
        "n": len(present),
        "median": statistics.median(present) if present else None,
        "min": min(present) if present else None,
        "max": max(present) if present else None,
    }


def summarize_cell(summary: dict[str, Any]) -> dict[str, Any]:
    """The per-cell block: detectors per scorer, the state machine, effects and e-values."""

    chains = summary["chains"]
    alarms = [chain["first_alarms"] for chain in chains]
    horizon = int(summary["post_change_windows"])
    scorers = list(summary["scorers"])
    detectors: dict[str, Any] = {}
    for scorer in scorers:
        detectors[scorer] = {}
        for detector in DETECTORS:
            entries = [fa["detectors"][scorer][detector] for fa in alarms]
            clean = [entry for entry in entries if not entry["pre_change"]]
            block = {
                "pre_change": _rate(len(entries) - len(clean), len(entries)),
                "eligible": len(clean),
                **detection_block([entry["delay"] for entry in clean], horizon),
            }
            if detector == "pooled":
                block["all_chains"] = detection_block([e["delay"] for e in entries], horizon)
            detectors[scorer][detector] = block
        warnings = [fa["detectors"][scorer]["eprocess"] for fa in alarms]
        clean_warnings = [entry for entry in warnings if not entry["warning_pre_change"]]
        detectors[scorer]["eprocess_warning"] = {
            "pre_change": _rate(len(warnings) - len(clean_warnings), len(warnings)),
            "eligible": len(clean_warnings),
            **detection_block([entry["warning_delay"] for entry in clean_warnings], horizon),
        }
    states = [fa["state"] for fa in alarms]
    eligible = [state for state in states if state["eligible"]]
    ineligible = [fa["replication"] for fa in alarms if not fa["state"]["eligible"]]
    first_rules: Counter[str] = Counter()
    for chain in chains:
        windows = chain["first_alarms"]["state"]["pre_change_drift_windows"]
        if windows:
            first_rules[str(chain["verdicts"][windows[0] - 1]["rule_fired"])] += 1
    after_rules = Counter(
        str(state["first_drift_at_or_after_change_rule"])
        for state in eligible
        if state["first_drift_at_or_after_change"] is not None
    )
    unconditional = {
        str(d): _rate(
            sum(
                1
                for state in states
                if state["eligible"]
                and state["state_delay"] is not None
                and state["state_delay"] <= d
            ),
            len(states),
        )
        for d in WITHIN
    }
    primary = str(summary["primary_scorer"])
    return {
        "cell": summary["cell"],
        "part": summary["part"],
        "panel_size": summary["panel_size"],
        "samples": summary["samples"],
        "kind": summary["kind"],
        "level": summary["level"],
        "primary_scorer": primary,
        "pre_change_windows": summary["pre_change_windows"],
        "post_change_windows": horizon,
        "change_window": summary["change_window"],
        "replications": summary["replications"],
        "chains": len(chains),
        "panel_digest": summary["panel_digest"],
        "config_digest": summary["config_digest"],
        "archive_sha256": summary["archive_sha256"],
        "timing": summary["timing"],
        "detectors": detectors,
        "state": {
            "ineligible": _rate(len(ineligible), len(states)),
            "ineligible_replications": ineligible,
            "pre_change_drift": _rate(
                sum(1 for state in states if state["pre_change_drift_windows"]), len(states)
            ),
            "pre_change_first_rule": dict(sorted(first_rules.items())),
            "drift": detection_block([state["state_delay"] for state in eligible], horizon),
            "warning_or_drift": detection_block(
                [state["warning_delay"] for state in eligible], horizon
            ),
            "first_drift_rule": dict(sorted(after_rules.items())),
            "unconditional_within": unconditional,
        },
        "effects": {
            scorer: {
                "T_post": _spread([fa["effects"][scorer]["T_post_mean"] for fa in alarms]),
                "T_pre": _spread([fa["effects"][scorer]["T_pre_mean"] for fa in alarms]),
            }
            for scorer in scorers
        },
        "e_before_change": {
            scorer: _range([fa["effects"][scorer]["e_before_change"] for fa in alarms])
            for scorer in scorers
        },
    }


# --- shared windows and distinct quiet chains ------------------------------------


def _comparable(record: dict[str, Any]) -> dict[str, Any]:
    """The fields of a verdict record that shared quiet windows must agree on."""

    return {
        "state": record["state"],
        "rule_fired": record["rule_fired"],
        "pooled": {
            scorer: {key: block[key] for key in ("T", "p", "p_holm", "rejected")}
            for scorer, block in record["pooled"].items()
        },
        "sequential": {
            scorer: {
                key: block[key] for key in ("cusum_alarm", "ph_alarm", "e_alarm", "e", "e_max")
            }
            for scorer, block in record["sequential"].items()
        },
    }


def geometry_key(summary: dict[str, Any]) -> str:
    return f"p{int(summary['panel_size']):02d}-n{int(summary['samples']):02d}"


def shared_window_check(summaries: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Verify that cells at one geometry share their quiet windows replication by replication.

    For every geometry the cell with the most quiet windows is the reference;
    every other cell's pre-change verdict records must equal the reference's
    over the quiet windows they have in common (protocol
    ``run.shared_window_check``). A difference raises ``RunError``: it is a
    data error, not a result.
    """

    groups: dict[str, list[dict[str, Any]]] = {}
    for summary in summaries:
        groups.setdefault(geometry_key(summary), []).append(summary)
    report: dict[str, Any] = {}
    for key, cells in groups.items():
        reference = max(cells, key=lambda s: int(s["pre_change_windows"]))
        by_replication = {chain["replication"]: chain for chain in reference["chains"]}
        differences: list[dict[str, Any]] = []
        compared = 0
        for cell in cells:
            if cell is reference:
                continue
            common = min(int(cell["pre_change_windows"]), int(reference["pre_change_windows"]))
            for chain in cell["chains"]:
                other = by_replication.get(chain["replication"])
                if other is None or common == 0:
                    continue
                compared += 1
                for index in range(common):
                    left = _comparable(chain["verdicts"][index])
                    right = _comparable(other["verdicts"][index])
                    if left != right and len(differences) < MISMATCH_LIMIT:
                        differences.append(
                            {
                                "cell": cell["cell"],
                                "reference": reference["cell"],
                                "replication": chain["replication"],
                                "window": index + 1,
                            }
                        )
        report[key] = {
            "reference": reference["cell"],
            "cells": [cell["cell"] for cell in cells],
            "chains_compared": compared,
            "agree": not differences,
            "differences": differences,
        }
    failed = [key for key, block in report.items() if not block["agree"]]
    if failed:
        raise RunError(
            "cells at one geometry disagree on their shared quiet windows: "
            + json.dumps({key: report[key]["differences"][:5] for key in failed})
        )
    return report


def distinct_quiet_cells(summaries: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """One cell per geometry and quiet length, the carrier of the distinct quiet chains."""

    chosen: dict[str, dict[str, Any]] = {}
    for summary in summaries:
        quiet = int(summary["pre_change_windows"])
        if quiet == 0:
            continue
        key = f"{geometry_key(summary)}-q{quiet:02d}"
        chosen.setdefault(key, summary)
    return chosen


def pre_change_false_alarms(summary: dict[str, Any], note: str | None) -> dict[str, Any]:
    """S-C3 for one carrier cell: per detector and scorer, the union, and the state machine."""

    alarms = [chain["first_alarms"] for chain in summary["chains"]]
    total = len(alarms)
    scorers = list(summary["scorers"])
    detectors: dict[str, Any] = {}
    for detector in DETECTORS:
        per_scorer = {
            scorer: _rate(
                sum(1 for fa in alarms if fa["detectors"][scorer][detector]["pre_change"]),
                total,
            )
            for scorer in scorers
        }
        union = sum(
            1
            for fa in alarms
            if any(fa["detectors"][scorer][detector]["pre_change"] for scorer in scorers)
        )
        detectors[detector] = {"per_scorer": per_scorer, "union": _rate(union, total)}
    first_rules: Counter[str] = Counter()
    for chain in summary["chains"]:
        windows = chain["first_alarms"]["state"]["pre_change_drift_windows"]
        if windows:
            first_rules[str(chain["verdicts"][windows[0] - 1]["rule_fired"])] += 1
    return {
        "cell": summary["cell"],
        "panel_size": summary["panel_size"],
        "samples": summary["samples"],
        "quiet_windows": summary["pre_change_windows"],
        "note": note,
        "detectors": detectors,
        "state": {
            "drift_before_change": _rate(
                sum(1 for fa in alarms if fa["state"]["pre_change_drift_windows"]), total
            ),
            "first_rule": dict(sorted(first_rules.items())),
            "sticky_before_change": _rate(
                sum(1 for fa in alarms if fa["state"]["pre_change_sticky"]), total
            ),
        },
    }


# --- H-C1 ------------------------------------------------------------------------


def _critical_count(n: int, alpha: float, p0: float = H_C1_P0) -> int | None:
    """The largest count whose one-sided (below) exact p-value is at most ``alpha``."""

    counts = [k for k in range(n + 1) if binomial_cdf(k, n, p0) <= alpha]
    return max(counts) if counts else None


def h_c1(cells: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """H-C1 over the eligible chains of the EXP-D operating-point cells, Holm across the family."""

    panel, samples, quiet = EXP_D_GEOMETRY
    rows: list[dict[str, Any]] = []
    for cell in cells:
        if (
            cell["part"] == "C1"
            and cell["panel_size"] == panel
            and cell["samples"] == samples
            and cell["pre_change_windows"] == quiet
            and cell["level"] in H_C1_LEVELS
        ):
            drift = cell["state"]["drift"]
            n = drift["total"]
            count = drift["within"][str(H_C1_WITHIN)]["count"]
            estimable = n > 0
            raw = binomial_cdf(count, n, H_C1_P0) if estimable else 1.0
            first_step = H_C1_ALPHA / H_C1_FAMILY
            critical = _critical_count(n, first_step) if estimable else None
            power = None
            if estimable:
                power = {
                    str(rate): 0.0 if critical is None else binomial_cdf(critical, n, rate)
                    for rate in H_C1_POWER_RATES
                }
            rows.append(
                {
                    "cell": cell["cell"],
                    "kind": cell["kind"],
                    "level": cell["level"],
                    "eligible": n,
                    "ineligible_replications": cell["state"]["ineligible_replications"],
                    "within_2": _rate(count, n),
                    "unconditional_within_2": cell["state"]["unconditional_within"]["2"],
                    "estimable": estimable,
                    "raw_p": raw,
                    "unadjusted_flag": bool(estimable and raw <= H_C1_ALPHA),
                    "critical_count_first_step": critical,
                    "critical_count_unadjusted": (
                        _critical_count(n, H_C1_ALPHA) if estimable else None
                    ),
                    "power_first_step": power,
                }
            )
    adjusted = holm([row["raw_p"] for row in rows]) if rows else []
    for row, p in zip(rows, adjusted, strict=True):
        row["holm_p"] = p
        row["falsified_after_holm"] = bool(row["estimable"] and p <= H_C1_ALPHA)
    return {
        "p0": H_C1_P0,
        "within_windows": H_C1_WITHIN,
        "family_alpha": H_C1_ALPHA,
        "planned_family_size": H_C1_FAMILY,
        "family_size": len(rows),
        "cells": rows,
        "falsified_after_holm": [row["cell"] for row in rows if row["falsified_after_holm"]],
        "not_estimable": [row["cell"] for row in rows if not row["estimable"]],
    }


# --- H-C2 and the quiet-length table ---------------------------------------------


def _find(summaries: Sequence[dict[str, Any]], **where: Any) -> dict[str, Any] | None:
    for summary in summaries:
        if all(summary[key] == value for key, value in where.items()):
            return summary
    return None


def h_c2(summaries: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """H-C2 through the pre-registered helper, with the quiet-length table per level."""

    panel, samples, c1_quiet = EXP_D_GEOMETRY
    cells: dict[str, dict[int, list[dict[str, Any]]]] = {}
    replications: set[int] = set()
    missing: list[str] = []
    for level in H_C2_LEVELS:
        cells[level] = {}
        for quiet in (0, 28):
            cell = _find(
                summaries,
                part="C3",
                kind="match",
                level=level,
                panel_size=panel,
                samples=samples,
                pre_change_windows=quiet,
            )
            if cell is None:
                missing.append(f"C3 match {level} q{quiet}")
                continue
            replications.add(int(cell["replications"]))
            cells[level][quiet] = [chain["first_alarms"] for chain in cell["chains"]]
    if missing or len(replications) != 1:
        return {
            "computed": False,
            "reason": "missing cells " + ", ".join(missing)
            if missing
            else f"C3 cells plan different replication counts {sorted(replications)}",
        }
    result = summarize_h_c2(cells, replications=replications.pop())
    result["computed"] = True
    result["by_quiet_length"] = {}
    for level in H_C2_LEVELS:
        table: dict[str, Any] = {}
        medians: list[tuple[int, int]] = []
        for quiet in (0, 7, c1_quiet, 28):
            cell = _find(
                summaries,
                part="C3" if quiet != c1_quiet else "C1",
                kind="match",
                level=level,
                panel_size=panel,
                samples=samples,
                pre_change_windows=quiet,
            )
            if cell is None:
                table[str(quiet)] = None
                continue
            chains = cell["chains"]
            if quiet == c1_quiet:
                chains = chains[: int(summaries_replications(summaries, level))]
            entries = [
                chain["first_alarms"]["detectors"]["normalized_match"]["eprocess"]
                for chain in chains
            ]
            clean = [entry for entry in entries if not entry["pre_change"]]
            block = detection_block([entry["delay"] for entry in clean], H_C2_HORIZON)
            table[str(quiet)] = {
                "cell": cell["cell"],
                "chains": len(entries),
                "pre_change_alarms": len(entries) - len(clean),
                **block,
                "e_before_change": _range(
                    [
                        chain["first_alarms"]["effects"]["normalized_match"]["e_before_change"]
                        for chain in chains
                    ]
                ),
            }
            if isinstance(block["median"], int):
                medians.append((quiet, block["median"]))
        slope = None
        if len(medians) == 4:
            xs, ys = [m[0] for m in medians], [m[1] for m in medians]
            x_mean, y_mean = statistics.fmean(xs), statistics.fmean(ys)
            slope = sum((x - x_mean) * (y - y_mean) for x, y in medians) / sum(
                (x - x_mean) ** 2 for x in xs
            )
        result["by_quiet_length"][level] = {
            "quiet_lengths": table,
            "median_slope_per_quiet_window": slope,
            "slope_note": "exploratory; computed only when all four medians are observed",
        }
    return result


def summaries_replications(summaries: Sequence[dict[str, Any]], level: str) -> int:
    """The C3 replication count at ``level``, the C3 sample size inside the C1 cell."""

    panel, samples, _ = EXP_D_GEOMETRY
    cell = _find(
        summaries,
        part="C3",
        kind="match",
        level=level,
        panel_size=panel,
        samples=samples,
        pre_change_windows=28,
    )
    assert cell is not None  # h_c2 only calls this once the C3 cells are known to exist
    return int(cell["replications"])


# --- S-C4 ------------------------------------------------------------------------


def s_c4(cells: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Window size: the match kind at levels 0.1 and 0.2 across N, from the cell blocks."""

    panel, _, quiet = EXP_D_GEOMETRY
    out: dict[str, Any] = {}
    for level in S_C4_LEVELS:
        rows: dict[str, Any] = {}
        for cell in cells:
            if (
                cell["kind"] == "match"
                and cell["level"] == level
                and cell["panel_size"] == panel
                and cell["pre_change_windows"] == quiet
            ):
                primary = cell["primary_scorer"]
                rows[str(cell["samples"])] = {
                    "cell": cell["cell"],
                    "state": {
                        key: cell["state"]["drift"][key]
                        for key in ("within", "median", "total")
                    },
                    "detectors": {
                        detector: {
                            key: cell["detectors"][primary][detector][key]
                            for key in ("within", "median", "pre_change", "eligible")
                        }
                        for detector in DETECTORS
                    },
                }
        out[level] = dict(sorted(rows.items(), key=lambda item: int(item[0])))
    return out


# --- S-C5 ------------------------------------------------------------------------


def _series(chain: dict[str, Any], scorer: str) -> list[float] | None:
    values = [record["pooled"][scorer]["T"] for record in chain["verdicts"]]
    if any(value is None for value in values):
        return None
    return [float(value) for value in values]


def _recorded_first(chain: dict[str, Any], scorer: str, field: str) -> int | None:
    for record in chain["verdicts"]:
        if record["sequential"][scorer][field]:
            return int(record["window_index"])
    return None


def _rerun_first(values: Sequence[float], detector: str, params: tuple[float, float]) -> int | None:
    if detector == "cusum":
        index = cusum(values, k=params[0], h=params[1]).alarm_index
    else:
        index = page_hinkley(values, delta=params[0], threshold=params[1]).alarm_index
    return None if index is None else index + 1


def default_check(summaries: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Rerun both heuristics at the shipped defaults over every recorded T series.

    Returns the chains that reproduce their recorded alarm windows (the
    grid runs on these) and the mismatches, which the summary reports.
    """

    passed: set[tuple[str, int]] = set()
    mismatches: list[dict[str, Any]] = []
    checked = 0
    for summary in summaries:
        for chain in summary["chains"]:
            checked += 1
            key = (str(summary["cell"]), int(chain["replication"]))
            ok = True
            for scorer in summary["scorers"]:
                values = _series(chain, scorer)
                if values is None:
                    ok = False
                    mismatches.append(
                        {
                            "cell": key[0],
                            "replication": key[1],
                            "scorer": scorer,
                            "detector": "none",
                            "reason": "missing T",
                        }
                    )
                    continue
                for detector, params, field in (
                    ("cusum", CUSUM_DEFAULT, "cusum_alarm"),
                    ("page_hinkley", PH_DEFAULT, "ph_alarm"),
                ):
                    recorded = _recorded_first(chain, scorer, field)
                    rerun = _rerun_first(values, detector, params)
                    if recorded != rerun:
                        ok = False
                        mismatches.append(
                            {
                                "cell": key[0],
                                "replication": key[1],
                                "scorer": scorer,
                                "detector": detector,
                                "recorded": recorded,
                                "rerun": rerun,
                            }
                        )
            if ok:
                passed.add(key)
    return {
        "chains_checked": checked,
        "chains_passed": len(passed),
        "mismatches": mismatches[:MISMATCH_LIMIT],
        "mismatch_count": len(mismatches),
        "passed": passed,
    }


def _union_first(
    chain: dict[str, Any],
    scorers: Sequence[str],
    detector: str,
    params: tuple[float, float],
    limit: int | None = None,
) -> int | None:
    """The first alarm window on any scorer when the detector reruns at ``params``."""

    first: int | None = None
    for scorer in scorers:
        values = _series(chain, scorer)
        assert values is not None  # the default check kept this chain
        hit = _rerun_first(values[:limit] if limit else values, detector, params)
        if hit is not None and (first is None or hit < first):
            first = hit
    return first


def _exp_a_a2_chains(exp_a_run_dir: Path | None) -> dict[str, Any] | None:
    """The EXP-A A2 cell at panel 24 by N 10, read from the EXP-A run directory."""

    if exp_a_run_dir is None:
        return None
    manifest_path = exp_a_run_dir / "manifest.json"
    if not manifest_path.is_file():
        raise RunError(f"{exp_a_run_dir} is not a run directory (no manifest.json)")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    candidates = [
        exp_a_run_dir / "cells" / "A2-p24-n10.json",
        exp_a_run_dir / "cells" / "A2-p24-n10.json.gz",
    ]
    path = next((p for p in candidates if p.exists()), None)
    if path is None:
        raise RunError(f"{exp_a_run_dir} has no A2-p24-n10 cell summary")
    cell = read_cell_summary(path)
    return {
        "run_id": manifest["run_id"],
        "profile": manifest["profile"],
        "protocol_digest": manifest["protocol"]["digest"],
        "scorers": list(cell["scorers"]),
        "chains": [
            {"replication": rep["replication"], "verdicts": rep["verdicts"]}
            for rep in cell["replications_detail"]
        ],
    }


def s_c5(summaries: Sequence[dict[str, Any]], exp_a_run_dir: Path | None) -> dict[str, Any]:
    """Offline recalibration grid of CUSUM and Page-Hinkley from the recorded T series."""

    check = default_check(summaries)
    passed: set[tuple[str, int]] = check.pop("passed")
    panel, samples, c1_quiet = EXP_D_GEOMETRY
    null_cell = _find(
        summaries,
        part="C3",
        panel_size=panel,
        samples=samples,
        pre_change_windows=S_C5_NULL_WINDOWS,
    )
    null_chains: list[dict[str, Any]] = []
    null_scorers: list[str] = []
    if null_cell is not None:
        null_scorers = list(null_cell["scorers"])
        null_chains = [
            c for c in null_cell["chains"] if (null_cell["cell"], c["replication"]) in passed
        ]
    delay_cells = [
        s
        for s in summaries
        if s["part"] == "C1"
        and s["level"] == S_C5_LEVEL
        and s["panel_size"] == panel
        and s["samples"] == samples
        and s["pre_change_windows"] == c1_quiet
    ]
    a2 = _exp_a_a2_chains(exp_a_run_dir)
    a2_usable = a2 is not None and a2["profile"] == "full"
    grids: dict[str, Any] = {}
    for detector, grid in (("cusum", CUSUM_GRID), ("page_hinkley", PH_GRID)):
        rows: list[dict[str, Any]] = []
        for params in grid:
            row: dict[str, Any] = {"params": list(params)}
            if null_chains:
                hits = sum(
                    1
                    for chain in null_chains
                    if _union_first(chain, null_scorers, detector, params, S_C5_NULL_WINDOWS)
                    is not None
                )
                row["c3_false_alarm"] = _rate(hits, len(null_chains))
            else:
                row["c3_false_alarm"] = None
            if a2 is not None:
                hits = sum(
                    1
                    for chain in a2["chains"]
                    if _union_first(chain, a2["scorers"], detector, params) is not None
                )
                row["a2_false_alarm"] = _rate(hits, len(a2["chains"]))
            else:
                row["a2_false_alarm"] = None
            kinds: dict[str, Any] = {}
            for cell in delay_cells:
                delays: list[int] = []
                pre = misses = 0
                for chain in cell["chains"]:
                    if (cell["cell"], chain["replication"]) not in passed:
                        continue
                    first = _union_first(chain, list(cell["scorers"]), detector, params)
                    if first is None:
                        misses += 1
                    elif first < cell["change_window"]:
                        pre += 1
                    else:
                        delays.append(first - cell["change_window"] + 1)
                kinds[cell["kind"]] = {
                    "mean_delay": statistics.fmean(delays) if delays else None,
                    "alarms": len(delays),
                    "misses": misses,
                    "pre_change": pre,
                }
            row["delay_level_0.2"] = kinds
            means = [block["mean_delay"] for block in kinds.values()]
            row["mean_delay_over_kinds"] = (
                statistics.fmean(means) if means and all(m is not None for m in means) else None
            )
            rows.append(row)
        recommended = None
        if a2_usable:
            candidates = [
                row
                for row in rows
                if row["a2_false_alarm"] is not None
                and row["a2_false_alarm"]["total"]
                and row["a2_false_alarm"]["ci95"][1] <= S_C5_UPPER_BOUND
                and row["mean_delay_over_kinds"] is not None
            ]
            if candidates:
                best = min(candidates, key=lambda row: row["mean_delay_over_kinds"])
                recommended = {
                    "params": best["params"],
                    "mean_delay_over_kinds": best["mean_delay_over_kinds"],
                }
        grids[detector] = {
            "default": list(CUSUM_DEFAULT if detector == "cusum" else PH_DEFAULT),
            "grid": rows,
            "recommended": recommended,
            "recommendation_withheld": None
            if recommended is not None
            else (
                "no EXP-A full run supplied"
                if not a2_usable
                else "no pair meets the false alarm bound"
            ),
        }
    return {
        "exploratory": True,
        "selection_basis": "union over the configured scorers; the first alarm on any scorer",
        "default_check": check,
        "null_chains": {
            "cell": None if null_cell is None else null_cell["cell"],
            "chains": len(null_chains),
        },
        "exp_a": None
        if a2 is None
        else {key: a2[key] for key in ("run_id", "profile", "protocol_digest")},
        **grids,
    }


# --- export and provenance -------------------------------------------------------


def export(
    cells: Sequence[dict[str, Any]], h_c1_block: dict[str, Any], s_c3_block: dict[str, Any]
) -> dict[str, Any]:
    """The EXP-D export: D90 per kind at level 0.2 over the eligible chains, and the bound."""

    panel, samples, quiet = EXP_D_GEOMETRY
    failing = set(h_c1_block["falsified_after_holm"]) | set(h_c1_block["not_estimable"])
    d90: dict[str, Any] = {}
    for cell in cells:
        if (
            cell["part"] == "C1"
            and cell["level"] == S_C5_LEVEL
            and cell["panel_size"] == panel
            and cell["samples"] == samples
            and cell["pre_change_windows"] == quiet
        ):
            d90[cell["kind"]] = {
                "cell": cell["cell"],
                "d90": cell["state"]["drift"]["p90"],
                "excluded": cell["cell"] in failing,
            }
    included = [block["d90"] for block in d90.values() if not block["excluded"]]
    censored = [value for value in included if not isinstance(value, int)]
    bound: int | str | None
    if not included:
        bound = None
    elif censored:
        bound = str(censored[0])
    else:
        bound = max(int(value) for value in included)
    carrier = s_c3_block.get(f"p{panel:02d}-n{samples:02d}-q{quiet:02d}")
    sticky = None if carrier is None else carrier["state"]["sticky_before_change"]
    return {
        "to": "EXP-D",
        "d90_level_0.2_by_kind": d90,
        "bound_days": bound,
        "kinds_excluded": sorted(kind for kind, block in d90.items() if block["excluded"]),
        "sticky_pre_change_rate_q14": sticky,
        "condition": (
            "a declared switch whose realised effect on at least one configured scorer is 0.2 "
            "or more in absolute value and whose monitor carries no sticky alarm from before "
            "the switch"
        ),
    }


def provenance(
    run_dir: Path, manifest: dict[str, Any], summaries: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    """Whether this run can be confirmatory: profile, status, tree, digests, grid and chains.

    A cell is complete when its summary carries the manifest's profile and
    exactly the planned replications 0..R-1 of the frozen protocol, in
    order; the paired H-C2 analysis relies on that.
    """

    frozen = load_protocol(run_dir / "protocol.frozen.json")
    planned = {cell.name: cell for cell in chain_cells(frozen, str(manifest["profile"]))}
    expected = set(planned)
    present = {str(summary["cell"]) for summary in summaries}
    digests_match = all(summary["protocol_digest"] == frozen.digest for summary in summaries)
    incomplete = sorted(
        str(summary["cell"])
        for summary in summaries
        if summary.get("profile") != manifest["profile"]
        or str(summary["cell"]) not in planned
        or len(summary["chains"]) != planned[str(summary["cell"])].replications
        or any(
            chain["replication"] != index for index, chain in enumerate(summary["chains"])
        )
    )
    git = manifest.get("git", {})
    block = {
        "run_id": manifest["run_id"],
        "profile": manifest["profile"],
        "status": manifest["status"],
        "commit": git.get("commit"),
        "clean_tree": git.get("dirty") is False and not manifest.get("allow_dirty", False),
        "protocol_version": frozen.version,
        "protocol_digest": frozen.digest,
        "protocol_digest_matches_manifest": manifest["protocol"]["digest"] == frozen.digest,
        "cell_digests_match": digests_match,
        "complete_grid": expected == present,
        "cells_missing": sorted(expected - present),
        "cells_extra": sorted(present - expected),
        "cells_incomplete": incomplete,
        "only_cells": manifest.get("only_cells", []),
        "resume": manifest.get("resume", False),
    }
    block["confirmatory"] = bool(
        manifest["profile"] == "full"
        and manifest["status"] == "completed"
        and block["clean_tree"]
        and block["protocol_digest_matches_manifest"]
        and digests_match
        and block["complete_grid"]
        and not incomplete
        and not block["only_cells"]
    )
    return block


# --- the summary -----------------------------------------------------------------


def summarize_exp_c(run_dir: Path, exp_a_run_dir: Path | None = None) -> dict[str, Any]:
    """Build the EXP-C summary for one run directory."""

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    order = [entry["cell"] for entry in manifest.get("cells", [])]
    paths = [summary_path(run_dir, name) for name in order]
    missing = [path.name for path in paths if not path.exists()]
    if not paths or missing:
        raise RunError(f"{run_dir} lacks cell summaries: {missing or 'none listed'}")
    summaries = [read_cell_summary(path) for path in paths]
    shared = shared_window_check(summaries)
    cells = [summarize_cell(summary) for summary in summaries]
    carriers = distinct_quiet_cells(summaries)
    s_c3_block: dict[str, Any] = {}
    longest: dict[str, int] = {}
    for summary in carriers.values():
        key = geometry_key(summary)
        longest[key] = max(longest.get(key, 0), int(summary["pre_change_windows"]))
    for key, summary in carriers.items():
        quiet = int(summary["pre_change_windows"])
        geometry = geometry_key(summary)
        note = (
            f"prefix of the chains with {longest[geometry]} quiet windows at this geometry"
            if quiet < longest[geometry]
            else None
        )
        s_c3_block[key] = pre_change_false_alarms(summary, note)
    h_c1_block = h_c1(cells)
    return {
        "format": SUMMARY_FORMAT,
        "experiment": manifest["experiment"],
        "run_ids": [manifest["run_id"]],
        "profile": manifest["profile"],
        "protocol": manifest["protocol"],
        "config_digest": manifest["config_digest"],
        "provenance": provenance(run_dir, manifest, summaries),
        "shared_window_check": shared,
        "cells": cells,
        "h_c1": h_c1_block,
        "h_c2": h_c2(summaries),
        "s_c3": s_c3_block,
        "s_c4": s_c4(cells),
        "s_c5": s_c5(summaries, exp_a_run_dir),
        "export": export(cells, h_c1_block, s_c3_block),
    }


def write_summary(run_dir: Path, root: Path, exp_a_run_dir: Path | None = None) -> Path:
    """Write the EXP-C summary of ``run_dir`` under ``analysis/generated/`` and return its path."""

    summary = summarize_exp_c(run_dir, exp_a_run_dir)
    out_dir = root / "analysis" / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"exp_c_{summary['run_ids'][0]}.json"
    path.write_text(
        json.dumps(summary, indent=1, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )
    return path
