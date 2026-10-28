"""The EXP-A runner on a tiny protocol: run directory, manifest, registry, refusals."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from epicormic_lab import exp_a
from epicormic_lab.exp_a import (
    EXPERIMENT_DIR,
    CellJob,
    RunError,
    monitor_id,
    run_cell,
    run_experiment,
    seed_document,
    verdict_record,
    window_id,
)
from epicormic_lab.protocol import Cell, ProtocolError, load_protocol

PROTOCOL = Path("experiments") / "exp_a_calibration" / "protocol.json"


def _payload(with_sequential: bool) -> dict[str, Any]:
    sequential: dict[str, Any] = {"cusum": None, "page_hinkley": None, "eprocess": None}
    if with_sequential:
        sequential = {
            "cusum": {
                "s_plus": "0.1",
                "s_minus": "0.05",
                "k": "0.1",
                "h": "0.4",
                "windows": 1,
                "alarm": False,
            },
            "page_hinkley": {
                "excursion": "0.02",
                "delta": "0.05",
                "lambda": "0.5",
                "windows": 1,
                "alarm": False,
            },
            "eprocess": {
                "e": "1.5",
                "log_e": "0.4",
                "max_e": "2.0",
                "threshold": "20",
                "observations": 40,
                "mu0": "0.9",
                "baseline_observations": 40,
                "ties_excluded": 0,
                "alarm": False,
                "alarm_index": None,
            },
        }
    return {
        "current_window_id": "A1-r000-w01",
        "sequence_index": 1,
        "state": "stable",
        "rule_fired": "no rule fired",
        "sample_counts": {
            "baseline": 40,
            "current": 40,
            "current_refused": 0,
            "probes_below_n_min": [],
        },
        "scorers": {
            "normalized_match": {
                "pooled": {
                    "T": "-0.0375",
                    "p": "0.675662",
                    "p_holm": "1",
                    "probes": 8,
                    "rejected": False,
                },
                "sequential": sequential,
            }
        },
    }


def test_verdict_record_decodes_numbers_and_missing_detectors() -> None:
    record = verdict_record(_payload(True), 1, "node")
    assert record["pooled"]["normalized_match"]["T"] == pytest.approx(-0.0375)
    assert record["pooled"]["normalized_match"]["p_holm"] == 1.0
    seq = record["sequential"]["normalized_match"]
    assert seq["cusum_max"] == pytest.approx(0.1)
    assert seq["e_max"] == 2.0 and seq["e_alarm"] is False and seq["baseline_observations"] == 40
    record = verdict_record(_payload(False), 1, None)
    assert record["sequential"]["normalized_match"]["e_max"] is None
    assert record["node_id"] is None
    assert exp_a._number(None) is None
    assert exp_a._number(True) == 1.0
    assert exp_a._number(3) == 3.0
    assert exp_a._number("2.5") == 2.5


def test_ids_and_seed_document() -> None:
    assert window_id("A1", 3, 0) == "A1-r003-w00"
    assert monitor_id("A2", 12) == "A2-r012"
    protocol = load_protocol(PROTOCOL)
    document = seed_document(protocol, protocol.cells("full"))
    assert document["provider_seed"] == 20261028
    assert document["cells"]["A2-p24-n10"]["last_salt"] == 199 * 100_000 + 28 * 1_000
    assert document["cells"]["A1-p08-n05"]["seeds_per_window"] == 5


def _job(repo: Path, digest: str, cell: Cell, run_id: str = "exp-a-smoke-001") -> CellJob:
    return CellJob(
        root=str(repo),
        protocol_path=PROTOCOL.as_posix(),
        protocol_digest=digest,
        run_id=run_id,
        profile="smoke",
        run_dir=str(repo / EXPERIMENT_DIR / "runs" / run_id),
        cell=cell,
    )


def test_run_cell_writes_a_summary_with_verdicts_and_timing(repo: Path, tiny_digest: str) -> None:
    cell = Cell("A2", 8, 5, 1, 3, 2)
    summary = run_cell(_job(repo, tiny_digest, cell))
    assert summary["cell"] == "A2-p08-n05"
    assert summary["timing"]["observations"] == 2 * 4 * 8 * 5
    assert summary["timing"]["verdicts"] == 6
    assert len(summary["store_sha256"]) == 64
    assert summary["store_sidecars"] == []
    detail = summary["replications_detail"]
    assert [v["window_index"] for v in detail[0]["verdicts"]] == [1, 2, 3]
    assert detail[1]["salts"] == [100_000, 101_000, 102_000, 103_000]
    assert {v["state"] for rep in detail for v in rep["verdicts"]} <= {"stable", "warning", "drift"}
    written = json.loads(
        (
            repo / EXPERIMENT_DIR / "runs" / "exp-a-smoke-001" / "cells" / "A2-p08-n05.json"
        ).read_text(encoding="utf-8")
    )
    assert written["timing"]["verdicts"] == 6
    # Rerunning the cell starts from a fresh store and reproduces every verdict node id
    # (the store file itself carries timestamps and durations, so its digest differs).
    again = run_cell(_job(repo, tiny_digest, cell))
    node_ids = [v["node_id"] for rep in detail for v in rep["verdicts"]]
    rerun_ids = [v["node_id"] for rep in again["replications_detail"] for v in rep["verdicts"]]
    assert rerun_ids == node_ids


def test_run_cell_fails_on_short_windows_and_recompute_mismatch(
    repo: Path, tiny_digest: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    cell = Cell("A1", 8, 5, 1, 1, 1)
    real_recompute = exp_a.recompute_verdict
    monkeypatch.setattr(
        exp_a, "recompute_verdict", lambda *a, **k: (real_recompute(*a, **k)[0], False)
    )
    with pytest.raises(RunError, match="recomputed verdict differs"):
        run_cell(_job(repo, tiny_digest, cell))
    monkeypatch.undo()

    class Short:
        recorded = 1
        refused = 0

    monkeypatch.setattr(exp_a, "observe", lambda *a, **k: Short())
    with pytest.raises(RunError, match="recorded 1 of 40"):
        run_cell(_job(repo, tiny_digest, cell))


def test_run_experiment_smoke_end_to_end(repo: Path, tiny_digest: str) -> None:
    manifest = run_experiment(
        repo,
        protocol_path=PROTOCOL,
        expected_digest=tiny_digest,
        profile="smoke",
        run_id="exp-a-smoke-001",
        allow_dirty=True,
    )
    run_dir = repo / EXPERIMENT_DIR / "runs" / "exp-a-smoke-001"
    assert manifest["status"] == "completed"
    assert [c["cell"] for c in manifest["cells"]] == ["A1-p08-n05", "A2-p08-n05", "A3-p08-n03"]
    assert set(manifest["store_digests"]) == {"A1-p08-n05", "A2-p08-n05", "A3-p08-n03"}
    for name in ("protocol.frozen.json", "environment.json", "seed.json", "manifest.json"):
        assert (run_dir / name).is_file()
    assert (run_dir / "protocol.frozen.json").read_bytes() == (repo / PROTOCOL).read_bytes()
    registry = (repo / "experiments" / "run_registry.yaml").read_text(encoding="utf-8")
    assert registry.count("  - run_id:") == 1 and '"exp-a-smoke-001"' in registry
    a3 = json.loads((run_dir / "cells" / "A3-p08-n03.json").read_text(encoding="utf-8"))
    assert {v["state"] for rep in a3["replications_detail"] for v in rep["verdicts"]} == {"unknown"}
    with pytest.raises(RunError, match="exists"):
        run_experiment(
            repo,
            protocol_path=PROTOCOL,
            expected_digest=tiny_digest,
            profile="smoke",
            run_id="exp-a-smoke-001",
            allow_dirty=True,
        )


def test_run_experiment_resume_keeps_finished_cells_and_can_use_workers(
    repo: Path, tiny_digest: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = repo / EXPERIMENT_DIR / "runs" / "exp-a-smoke-002"
    cell = Cell("A1", 8, 5, 1, 1, 2)
    kept = run_cell(_job(repo, tiny_digest, cell, "exp-a-smoke-002"))
    (run_dir / "stores" / "A2-p08-n05.sqlite").write_bytes(b"partial")
    manifest = run_experiment(
        repo,
        protocol_path=PROTOCOL,
        expected_digest=tiny_digest,
        profile="smoke",
        run_id="exp-a-smoke-002",
        workers=2,
        resume=True,
        allow_dirty=True,
    )
    assert manifest["store_digests"]["A1-p08-n05"] == kept["store_sha256"]
    assert manifest["resume"] is True and manifest["workers"] == 2
    assert len(manifest["cells"]) == 3


def test_run_experiment_refusals(
    repo: Path, tiny_digest: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    common: dict[str, Any] = {"protocol_path": PROTOCOL, "profile": "smoke", "run_id": "r"}
    with pytest.raises(ProtocolError, match="registered under"):
        run_experiment(repo, expected_digest="0" * 64, **common)
    monkeypatch.setattr(
        exp_a, "check_installed", lambda: ["epicormic 0.1.0 is pinned but 9 is installed"]
    )
    with pytest.raises(RunError, match="pinned"):
        run_experiment(repo, expected_digest=tiny_digest, **common)
    monkeypatch.setattr(exp_a, "check_installed", list)
    monkeypatch.setattr(exp_a, "git_state", lambda root: {"commit": None, "dirty": None})
    with pytest.raises(RunError, match="clean, committed tree"):
        run_experiment(
            repo, expected_digest=tiny_digest, profile="full", run_id="r", protocol_path=PROTOCOL
        )
    with pytest.raises(RunError, match="unknown cells"):
        run_experiment(repo, expected_digest=tiny_digest, only_cells=("nope",), **common)


def test_run_experiment_marks_a_failed_run(
    repo: Path, tiny_digest: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(job: CellJob) -> dict[str, Any]:
        raise RunError("cell exploded")

    monkeypatch.setattr(exp_a, "run_cell", boom)
    with pytest.raises(RunError, match="exploded"):
        run_experiment(
            repo,
            protocol_path=PROTOCOL,
            expected_digest=tiny_digest,
            profile="smoke",
            run_id="exp-a-smoke-003",
            allow_dirty=True,
            only_cells=("A3-p08-n03",),
        )
    manifest = json.loads(
        (repo / EXPERIMENT_DIR / "runs" / "exp-a-smoke-003" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["status"] == "failed" and manifest["only_cells"] == ["A3-p08-n03"]
    assert "exp-a-smoke-003" not in (repo / "experiments" / "run_registry.yaml").read_text(
        encoding="utf-8"
    )
