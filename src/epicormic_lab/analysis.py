"""From cell summaries to the committed, value-free EXP-A summary.

``summarize_exp_a`` reads the ``cells/*.json`` files of one run directory and
computes exactly what the pre-registration's section 5 lists: per cell the
state counts and the drift rate with its Clopper-Pearson interval, the
one-sided exact binomial p-value against alpha and its Holm adjustment across
the A1 cells, the rule breakdown, the raw p-value uniformity diagnostics,
the sequential alarm rates over the horizon, and the pooled A1 rate.
``write_summary`` writes the result to ``analysis/generated/``, the only
place the paper reads numbers from.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from epicormic_lab.stats import binomial_sf, clopper_pearson, ecdf_at, holm, ks_uniform

SUMMARY_FORMAT = "epicormic-lab/exp-a-summary/v1"
ECDF_POINTS = (0.01, 0.05, 0.1, 0.5)
STATES = ("stable", "warning", "drift", "unknown")


def _rate(count: int, total: int, confidence: float = 0.95) -> dict[str, Any]:
    if total == 0:
        return {"count": 0, "total": 0, "rate": None, "ci95": None}
    low, high = clopper_pearson(count, total, confidence)
    return {"count": count, "total": total, "rate": count / total, "ci95": [low, high]}


def _first_window_verdicts(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """The first current-window verdict of every replication (independent across replications)."""

    return [rep["verdicts"][0] for rep in summary["replications_detail"] if rep["verdicts"]]


def _uniformity(verdicts: list[dict[str, Any]], scorers: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for scorer in scorers:
        pooled = [v["pooled"][scorer]["p"] for v in verdicts]
        values = [p for p in pooled if p is not None]
        out[scorer] = {
            "n": len(values),
            "ecdf": ecdf_at(values, ECDF_POINTS),
            "ks_distance": ks_uniform(values),
            "rejected_after_holm": sum(1 for v in verdicts if v["pooled"][scorer]["rejected"]),
        }
    return out


def _alarm_horizon(summary: dict[str, Any], scorers: list[str], alpha: float) -> dict[str, Any]:
    """Alarm rates of the three sequential detectors over the replication's full horizon."""

    detectors = {"eprocess": "e_alarm", "cusum": "cusum_alarm", "page_hinkley": "ph_alarm"}
    total = len(summary["replications_detail"])
    horizon = summary["current_windows"]
    out: dict[str, Any] = {"horizon_windows": horizon}
    for detector, key in detectors.items():
        per_scorer: dict[str, Any] = {}
        union_first: list[int | None] = []
        for rep in summary["replications_detail"]:
            first_any: int | None = None
            for scorer in scorers:
                hit = next(
                    (v["window_index"] for v in rep["verdicts"] if v["sequential"][scorer][key]),
                    None,
                )
                per_scorer.setdefault(scorer, []).append(hit)
                if hit is not None and (first_any is None or hit < first_any):
                    first_any = hit
            union_first.append(first_any)
        union_count = sum(1 for hit in union_first if hit is not None)
        out[detector] = {
            "per_scorer": {
                scorer: {
                    **_rate(sum(1 for h in hits if h is not None), total),
                    "first_alarm_window_counts": dict(
                        sorted(Counter(h for h in hits if h is not None).items())
                    ),
                }
                for scorer, hits in per_scorer.items()
            },
            "union": {
                **_rate(union_count, total),
                "first_alarm_window_counts": dict(
                    sorted(Counter(h for h in union_first if h is not None).items())
                ),
                "one_sided_p_vs_alpha": binomial_sf(union_count, total, alpha) if total else None,
            },
        }
    drift_first: list[int | None] = []
    first_rules: Counter[str] = Counter()
    for rep in summary["replications_detail"]:
        hit = next((v for v in rep["verdicts"] if v["state"] == "drift"), None)
        drift_first.append(None if hit is None else hit["window_index"])
        if hit is not None:
            first_rules[hit["rule_fired"]] += 1
    out["any_drift"] = {
        **_rate(sum(1 for h in drift_first if h is not None), total),
        "first_drift_window_counts": dict(
            sorted(Counter(h for h in drift_first if h is not None).items())
        ),
        "first_rule_fired": dict(first_rules),
    }
    return out


def summarize_cell(summary: dict[str, Any]) -> dict[str, Any]:
    """The per-cell block of the EXP-A summary."""

    scorers = list(summary["scorers"])
    alpha = float(summary["alpha"])
    first = _first_window_verdicts(summary)
    total = len(first)
    states = Counter(v["state"] for v in first)
    rules = Counter(v["rule_fired"] for v in first)
    drift = states.get("drift", 0)
    block: dict[str, Any] = {
        "cell": summary["cell"],
        "part": summary["part"],
        "panel_size": summary["panel_size"],
        "samples": summary["samples"],
        "replications": summary["replications"],
        "current_windows": summary["current_windows"],
        "alpha": alpha,
        "scorers": scorers,
        "panel_digest": summary["panel_digest"],
        "config_digest": summary["config_digest"],
        "store_sha256": summary["store_sha256"],
        "timing": summary["timing"],
        "first_window": {
            "states": {state: states.get(state, 0) for state in STATES},
            "rule_fired": dict(sorted(rules.items())),
            "drift": {
                **_rate(drift, total),
                "one_sided_p_vs_alpha": binomial_sf(drift, total, alpha) if total else None,
                "unadjusted_flag": bool(total and binomial_sf(drift, total, alpha) <= 0.05),
            },
            "warning": _rate(states.get("warning", 0), total),
            "unknown": _rate(states.get("unknown", 0), total),
            "uniformity": _uniformity(first, scorers),
        },
    }
    if summary["current_windows"] > 1:
        block["horizon"] = _alarm_horizon(summary, scorers, alpha)
    return block


def summarize_exp_a(run_dir: Path) -> dict[str, Any]:
    """Build the EXP-A summary for one run directory."""

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    cell_files = sorted((run_dir / "cells").glob("*.json"))
    if not cell_files:
        raise ValueError(f"{run_dir} has no cell summaries")
    cells = [
        summarize_cell(json.loads(path.read_text(encoding="utf-8"))) for path in cell_files
    ]
    a1 = [cell for cell in cells if cell["part"] == "A1"]
    raw = [cell["first_window"]["drift"]["one_sided_p_vs_alpha"] for cell in a1]
    adjusted = holm(raw) if a1 else []
    for cell, raw_p, adj_p in zip(a1, raw, adjusted, strict=True):
        cell["first_window"]["drift"]["holm_p_across_a1"] = adj_p
        cell["first_window"]["drift"]["falsified_after_holm"] = bool(adj_p <= 0.05)
        cell["first_window"]["drift"]["raw_p"] = raw_p
    pooled_count = sum(cell["first_window"]["drift"]["count"] for cell in a1)
    pooled_total = sum(cell["first_window"]["drift"]["total"] for cell in a1)
    a3 = [cell for cell in cells if cell["part"] == "A3"]
    return {
        "format": SUMMARY_FORMAT,
        "experiment": manifest["experiment"],
        "run_ids": [manifest["run_id"]],
        "profile": manifest["profile"],
        "protocol_digest": manifest["protocol"]["digest"],
        "config_digest": manifest["config_digest"],
        "cells": cells,
        "a1_pooled_drift": _rate(pooled_count, pooled_total),
        "a1_cells_falsified_after_holm": [
            cell["cell"] for cell in a1 if cell["first_window"]["drift"]["falsified_after_holm"]
        ],
        "a3_all_unknown": all(
            cell["first_window"]["states"]["unknown"] == cell["first_window"]["drift"]["total"]
            for cell in a3
        )
        if a3
        else None,
    }


def write_summary(run_dir: Path, root: Path) -> Path:
    """Write the EXP-A summary of ``run_dir`` under ``analysis/generated/`` and return its path."""

    summary = summarize_exp_a(run_dir)
    out_dir = root / "analysis" / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"exp_a_{summary['run_ids'][0]}.json"
    path.write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return path
