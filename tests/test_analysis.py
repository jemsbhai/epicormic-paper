"""From cell summaries to the committed summary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from epicormic_lab.analysis import summarize_cell, summarize_exp_a, write_summary
from epicormic_lab.exp_a import EXPERIMENT_DIR, run_experiment

PROTOCOL = Path("experiments") / "exp_a_calibration" / "protocol.json"


@pytest.fixture
def run_dir(repo: Path, tiny_digest: str) -> Path:
    run_experiment(
        repo,
        protocol_path=PROTOCOL,
        expected_digest=tiny_digest,
        profile="smoke",
        run_id="exp-a-smoke-009",
        allow_dirty=True,
    )
    return repo / EXPERIMENT_DIR / "runs" / "exp-a-smoke-009"


def test_summary_structure(repo: Path, run_dir: Path) -> None:
    summary = summarize_exp_a(run_dir)
    assert summary["run_ids"] == ["exp-a-smoke-009"]
    assert summary["a3_all_unknown"] is True
    cells = {cell["cell"]: cell for cell in summary["cells"]}
    a1 = cells["A1-p08-n05"]["first_window"]["drift"]
    assert a1["total"] == 2 and "holm_p_across_a1" in a1 and "falsified_after_holm" in a1
    assert sum(cells["A1-p08-n05"]["first_window"]["states"].values()) == 2
    uniformity = cells["A1-p08-n05"]["first_window"]["uniformity"]["normalized_match"]
    assert set(uniformity["ecdf"]) == {"0.01", "0.05", "0.1", "0.5"}
    horizon = cells["A2-p08-n05"]["horizon"]
    assert horizon["horizon_windows"] == 3
    assert set(horizon) == {"horizon_windows", "eprocess", "cusum", "page_hinkley", "any_drift"}
    assert horizon["eprocess"]["union"]["total"] == 2
    assert "horizon" not in cells["A1-p08-n05"]
    assert summary["a1_pooled_drift"]["total"] == 2
    path = write_summary(run_dir, repo)
    assert path == repo / "analysis" / "generated" / "exp_a_exp-a-smoke-009.json"
    assert json.loads(path.read_text(encoding="utf-8"))["format"] == summary["format"]


def test_summary_handles_alarms_and_empty_cells(run_dir: Path) -> None:
    cell = json.loads((run_dir / "cells" / "A2-p08-n05.json").read_text(encoding="utf-8"))
    first = cell["replications_detail"][0]["verdicts"]
    first[1]["state"] = "drift"
    first[1]["rule_fired"] = "e-process alarm for normalized_match"
    first[1]["sequential"]["normalized_match"]["e_alarm"] = True
    first[2]["sequential"]["output_chars"]["cusum_alarm"] = True
    block = summarize_cell(cell)
    assert block["horizon"]["eprocess"]["union"]["count"] == 1
    assert block["horizon"]["eprocess"]["union"]["first_alarm_window_counts"] == {2: 1}
    assert block["horizon"]["cusum"]["per_scorer"]["output_chars"]["count"] == 1
    assert block["horizon"]["any_drift"]["first_rule_fired"] == {
        "e-process alarm for normalized_match": 1
    }
    cell["replications_detail"] = []
    empty = summarize_cell(cell)
    assert empty["first_window"]["drift"]["rate"] is None
    assert empty["first_window"]["drift"]["one_sided_p_vs_alpha"] is None
    assert empty["horizon"]["eprocess"]["union"]["one_sided_p_vs_alpha"] is None


def test_summary_without_cells_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")
    (tmp_path / "cells").mkdir()
    with pytest.raises(ValueError, match="no cell summaries"):
        summarize_exp_a(tmp_path)


def test_summary_without_a1_or_a3_cells(repo: Path, run_dir: Path) -> None:
    for name in ("A1-p08-n05.json", "A3-p08-n03.json"):
        (run_dir / "cells" / name).unlink()
    summary = summarize_exp_a(run_dir)
    assert summary["a3_all_unknown"] is None
    assert summary["a1_pooled_drift"]["total"] == 0
    assert summary["a1_cells_falsified_after_holm"] == []
