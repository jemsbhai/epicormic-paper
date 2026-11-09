"""The EXP-C runner: cells, execution order, chains, archives, run directories and refusals."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from epicormic_lab import exp_c
from epicormic_lab.chains import ChainError
from epicormic_lab.exp_a import RunError
from epicormic_lab.exp_c import (
    CELL_SUMMARY_FORMAT,
    EXPERIMENT_DIR,
    ChainCell,
    ChainJob,
    archive_store,
    chain_cells,
    execution_order,
    finished_summary,
    monitor_id,
    project_full_profile,
    read_cell_summary,
    run_cell,
    run_experiment,
    seed_document,
    summary_path,
    write_cell_summary,
)
from epicormic_lab.protocol import ProtocolError, load_protocol, protocol_digest

from .conftest import EXP_C_PROTOCOL, tiny_c_document

PROTOCOL = Path("experiments") / "exp_c_sequential" / "protocol.json"


def test_chain_cell_names_and_geometry() -> None:
    cell = ChainCell("C1", 24, 10, "match", "0.2", 1, 14, 14, 100)
    assert cell.name == "C1-p24-n10-match-l200-q14"
    assert cell.level_thousandths == 200
    assert cell.current_windows == 28 and cell.windows_per_replication == 29
    assert cell.change_window == 15
    low = ChainCell("C3", 24, 10, "match", "0.05", 1, 0, 14, 50)
    assert low.name == "C3-p24-n10-match-l050-q00" and low.change_window == 1
    assert monitor_id(cell, 7) == "C1-p24-n10-match-l200-q14-r007"


def test_real_grid_enumerates_the_registered_workload_in_protocol_order() -> None:
    protocol = load_protocol(EXP_C_PROTOCOL)
    cells = chain_cells(protocol, "full")
    assert len(cells) == 35
    assert sum(cell.replications for cell in cells) == 1800
    assert sum(cell.replications * cell.current_windows for cell in cells) == 49_980
    nodes = sum(
        cell.replications * cell.windows_per_replication * cell.panel_size * cell.samples
        for cell in cells
    )
    assert nodes == 12_636_000  # about 12.6 million in the pre-registration (r4)
    # the superseded r3 carried the counts the sizing rule lowered
    r3 = load_protocol(EXP_C_PROTOCOL.with_name("protocol.2026-11-05-r3.json"))
    r3_cells = chain_cells(r3, "full")
    assert sum(cell.replications for cell in r3_cells) == 3000
    assert sum(cell.replications * cell.current_windows for cell in r3_cells) == 83_300
    assert cells[0].name == "C1-p24-n10-match-l050-q14"
    assert all(cell.replications == 2 for cell in chain_cells(protocol, "smoke"))
    order = execution_order(cells, protocol)
    names = [cell.name for cell in order]
    assert names[:6] == [
        "C3-p24-n10-match-l300-q00",
        "C3-p24-n10-match-l300-q07",
        "C3-p24-n10-match-l300-q28",
        "C3-p24-n10-match-l500-q00",
        "C3-p24-n10-match-l500-q07",
        "C3-p24-n10-match-l500-q28",
    ]
    levels = ("050", "100", "200", "300", "500")
    assert names[6:11] == [f"C1-p24-n10-match-l{level}-q14" for level in levels]
    assert names[11].startswith("C1-p24-n10-refusal")
    assert names[-4:] == [
        "C2-p24-n05-match-l100-q14",
        "C2-p24-n20-match-l100-q14",
        "C2-p24-n05-match-l200-q14",
        "C2-p24-n20-match-l200-q14",
    ]
    assert len(set(names)) == 35
    with pytest.raises(RunError, match="profile"):
        chain_cells(protocol, "nightly")


def test_chain_cells_refuses_unknown_kinds_and_bad_levels(repo: Path) -> None:
    path = repo / PROTOCOL
    document = json.loads(path.read_text(encoding="utf-8"))
    document["parts"]["C1"]["kinds"] = ["match", "latency"]
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(RunError, match="unknown drift kinds"):
        chain_cells(load_protocol(path), "smoke")
    document["parts"]["C1"]["kinds"] = ["match"]
    document["parts"]["C1"]["levels"] = ["1.5"]
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="drift level"):
        chain_cells(load_protocol(path), "smoke")
    document["parts"]["C1"]["levels"] = ["0.5", "0.50"]
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(RunError, match="one name"):
        chain_cells(load_protocol(path), "smoke")
    # a part outside the registered order runs after them, in protocol order
    document["parts"] = {
        "C9": {**document["parts"]["C1"], "levels": ["0.5"]},
        "C1": {**document["parts"]["C1"], "levels": ["0.5"]},
    }
    path.write_text(json.dumps(document), encoding="utf-8")
    protocol = load_protocol(path)
    ordered = execution_order(chain_cells(protocol, "smoke"), protocol)
    assert [c.part for c in ordered] == ["C1", "C9"]


def test_seed_document_records_every_source_of_randomness() -> None:
    protocol = load_protocol(EXP_C_PROTOCOL)
    document = seed_document(protocol, chain_cells(protocol, "full"))
    assert document["provider_seed"] == 20261029 == document["drifted_provider_seed"]
    assert document["analysis_seed"] == 0
    assert document["mixture"]["tag"] == "epicormic-lab/mixture/v1:"
    c3 = document["cells"]["C3-p24-n10-match-l300-q28"]
    assert c3["change_window"] == 29 and c3["windows_per_replication"] == 43
    assert c3["last_salt"] == 29 * 100_000 + 42 * 1_000  # 30 replications in r4 (50 in r3)
    assert document["cells"]["C2-p24-n20-match-l200-q14"]["seeds_per_window"] == 20


def test_cell_summary_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "cells" / "x.json.gz"
    write_cell_summary(path, {"b": 1, "a": [1.5, None]})
    assert read_cell_summary(path) == {"a": [1.5, None], "b": 1}
    # the gzip header carries no time, so equal content gives equal bytes
    again = tmp_path / "y.json.gz"
    write_cell_summary(again, {"b": 1, "a": [1.5, None]})
    assert again.read_bytes() == path.read_bytes()
    plain = tmp_path / "plain.json"
    plain.write_text('{"k": 2}', encoding="utf-8")
    assert read_cell_summary(plain) == {"k": 2}
    plain.write_text("[1]", encoding="utf-8")
    with pytest.raises(RunError, match="not a cell summary"):
        read_cell_summary(plain)


def _job(repo: Path, digest: str, cell: ChainCell, run_id: str = "exp-c-smoke-001") -> ChainJob:
    return ChainJob(
        root=str(repo),
        protocol_path=PROTOCOL.as_posix(),
        protocol_digest=digest,
        run_id=run_id,
        profile="smoke",
        run_dir=str(repo / EXPERIMENT_DIR / "runs" / run_id),
        cell=cell,
    )


def test_run_cell_observes_chains_archives_the_store_and_reproduces(
    repo: Path, tiny_c_digest: str
) -> None:
    cell = ChainCell("C3", 8, 5, "refusal", "1", 1, 2, 2, 2)
    summary = run_cell(_job(repo, tiny_c_digest, cell))
    run_dir = repo / EXPERIMENT_DIR / "runs" / "exp-c-smoke-001"
    assert summary["format"] == CELL_SUMMARY_FORMAT and summary["cell"] == cell.name
    assert summary["primary_scorer"] == "refusal" and summary["change_window"] == 3
    assert summary["timing"]["observations"] == 2 * 5 * 8 * 5
    assert summary["timing"]["verdicts"] == 8 and summary["timing"]["chains"] == 2
    assert summary["timing"]["seconds_per_chain"] > 0
    chains = summary["chains"]
    assert chains[1]["salts"] == [100_000, 101_000, 102_000, 103_000, 104_000]
    assert chains[0]["window_ids"][0] == "C3-r000-w00"
    assert chains[0]["monitor_id"] == "C3-p08-n05-refusal-l1000-q02-r000"
    first = chains[0]["first_alarms"]
    assert first["kind"] == "refusal" and first["level"] == "1" and first["replication"] == 0
    # every answer is refused from the change window on: detected at once
    assert first["detectors"]["refusal"]["pooled"]["delay"] == 1
    assert first["state"]["state_delay"] == 1 and first["state"]["eligible"] is True
    assert [v["window_index"] for v in chains[0]["verdicts"]] == [1, 2, 3, 4]
    # the store is archived, its digest recorded, and the uncompressed store gone
    stores = run_dir / "stores"
    assert sorted(p.name for p in stores.iterdir()) == [f"{cell.name}.zip"]
    assert summary["archive"] == f"stores/{cell.name}.zip" and summary["store_sidecars"] == []
    assert len(summary["archive_sha256"]) == 64 and summary["archive_bytes"] > 0
    with zipfile.ZipFile(stores / f"{cell.name}.zip") as archive:
        assert archive.namelist() == [f"{cell.name}.sqlite"]
        extracted = archive.read(f"{cell.name}.sqlite")
    import hashlib

    assert hashlib.sha256(extracted).hexdigest() == summary["store_sha256"]
    assert len(extracted) == summary["store_bytes"]
    written = read_cell_summary(summary_path(run_dir, cell.name))
    assert written["archive_sha256"] == summary["archive_sha256"]
    # a rerun starts from a fresh store and reproduces every verdict node id
    again = run_cell(_job(repo, tiny_c_digest, cell))
    assert [v["node_id"] for c in again["chains"] for v in c["verdicts"]] == [
        v["node_id"] for c in chains for v in c["verdicts"]
    ]


def test_run_cell_reports_chain_errors_with_the_cell(
    repo: Path, tiny_c_digest: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    cell = ChainCell("C1", 8, 5, "match", "0.5", 1, 1, 1, 1)

    def short(*args: Any, **kwargs: Any) -> int:
        raise ChainError("recorded 1 of 40")

    monkeypatch.setattr(exp_c, "observe_chain", short)
    with pytest.raises(RunError, match=f"{cell.name} replication 0: recorded 1 of 40"):
        run_cell(_job(repo, tiny_c_digest, cell))
    monkeypatch.undo()

    def mismatch(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        raise ChainError("w02: recomputed verdict differs")

    monkeypatch.setattr(exp_c, "analyze_chain", mismatch)
    with pytest.raises(RunError, match="recomputed verdict differs"):
        run_cell(_job(repo, tiny_c_digest, cell))


def test_archive_store_includes_sidecars(tmp_path: Path) -> None:
    (tmp_path / "c.sqlite").write_bytes(b"store")
    (tmp_path / "c.sqlite-wal").write_bytes(b"wal")
    result = archive_store(tmp_path, "c")
    assert result["store_sidecars"] == ["c.sqlite-wal"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["c.zip"]
    with zipfile.ZipFile(tmp_path / "c.zip") as archive:
        assert sorted(archive.namelist()) == ["c.sqlite", "c.sqlite-wal"]


def test_run_experiment_smoke_end_to_end(repo: Path, tiny_c_digest: str) -> None:
    manifest = run_experiment(
        repo,
        protocol_path=PROTOCOL,
        expected_digest=tiny_c_digest,
        profile="smoke",
        run_id="exp-c-smoke-001",
        allow_dirty=True,
    )
    run_dir = repo / EXPERIMENT_DIR / "runs" / "exp-c-smoke-001"
    assert manifest["status"] == "completed" and manifest["experiment"] == "EXP-C"
    assert manifest["cell_order"] == [
        "C3-p08-n05-match-l500-q00",
        "C3-p08-n05-match-l500-q04",
        "C1-p08-n05-match-l500-q02",
        "C1-p08-n05-refusal-l500-q02",
        "C2-p08-n10-match-l500-q02",
    ]
    assert [c["cell"] for c in manifest["cells"]] == manifest["cell_order"]
    assert set(manifest["store_digests"]) == set(manifest["cell_order"])
    for name in ("protocol.frozen.json", "environment.json", "seed.json", "manifest.json"):
        assert (run_dir / name).is_file()
    assert (run_dir / "protocol.frozen.json").read_bytes() == (repo / PROTOCOL).read_bytes()
    assert sorted(p.name for p in (run_dir / "stores").iterdir()) == [
        f"{name}.zip" for name in sorted(manifest["cell_order"])
    ]
    seeds = json.loads((run_dir / "seed.json").read_text(encoding="utf-8"))
    assert seeds["cells"]["C3-p08-n05-match-l500-q04"]["change_window"] == 5
    registry = (repo / "experiments" / "run_registry.yaml").read_text(encoding="utf-8")
    assert registry.count("  - run_id:") == 1 and '"exp-c-smoke-001"' in registry
    assert '"2026-10-29 EXP-C planned (mock arm)"' in registry
    # the shared quiet windows: the first two current windows of the q04 C3 chain
    # and the C1 chains at the same replication carry identical verdicts
    c3 = read_cell_summary(summary_path(run_dir, "C3-p08-n05-match-l500-q04"))
    c1 = read_cell_summary(summary_path(run_dir, "C1-p08-n05-refusal-l500-q02"))
    for rep in range(2):
        for index in range(2):
            left = c3["chains"][rep]["verdicts"][index]
            right = c1["chains"][rep]["verdicts"][index]
            assert left["pooled"] == right["pooled"] and left["state"] == right["state"]
    with pytest.raises(RunError, match="exists"):
        run_experiment(
            repo,
            protocol_path=PROTOCOL,
            expected_digest=tiny_c_digest,
            profile="smoke",
            run_id="exp-c-smoke-001",
            allow_dirty=True,
        )
    protocol = load_protocol(repo / PROTOCOL)
    projection = project_full_profile(protocol, manifest, 2)
    assert projection["cells_projected"] == 5 and projection["cells_missing"] == []
    assert projection["within_12_hours"] is True
    assert projection["makespan_hours"] <= projection["cpu_hours"]
    assert projection["makespan_hours"] >= projection["longest_cell_hours"]
    serial = project_full_profile(protocol, manifest, 1)
    assert serial["makespan_hours"] == pytest.approx(serial["cpu_hours"])
    partial = project_full_profile(protocol, {"cells": manifest["cells"][:2]}, 2)
    assert len(partial["cells_missing"]) == 3 and partial["within_12_hours"] is False
    with pytest.raises(RunError, match="workers"):
        project_full_profile(protocol, manifest, 0)


def test_run_experiment_resume_keeps_intact_cells_and_reruns_the_rest(
    repo: Path, tiny_c_digest: str
) -> None:
    run_id = "exp-c-smoke-002"
    run_dir = repo / EXPERIMENT_DIR / "runs" / run_id
    kept_cell = ChainCell("C3", 8, 5, "match", "0.5", 1, 0, 3, 2)
    kept = run_cell(_job(repo, tiny_c_digest, kept_cell, run_id))
    assert finished_summary(run_dir, kept_cell, run_id) is not None
    # a summary from another run, a missing archive, or a wrong digest: rerun
    other = ChainCell("C3", 8, 5, "match", "0.5", 1, 4, 3, 2)
    assert finished_summary(run_dir, other, run_id) is None
    write_cell_summary(summary_path(run_dir, other.name), {"format": "x"})
    assert finished_summary(run_dir, other, run_id) is None
    summary_path(run_dir, other.name).write_bytes(b"not gzip")
    assert finished_summary(run_dir, other, run_id) is None
    damaged = {**kept, "cell": other.name}
    write_cell_summary(summary_path(run_dir, other.name), damaged)
    assert finished_summary(run_dir, other, run_id) is None  # names another cell's archive
    damaged["archive"] = f"stores/{other.name}.zip"
    write_cell_summary(summary_path(run_dir, other.name), damaged)
    assert finished_summary(run_dir, other, run_id) is None  # archive is absent
    (run_dir / "stores" / f"{other.name}.zip").write_bytes(b"partial")
    assert finished_summary(run_dir, other, run_id) is None  # digest differs
    (run_dir / "stores" / f"{other.name}.sqlite").write_bytes(b"partial")
    manifest = run_experiment(
        repo,
        protocol_path=PROTOCOL,
        expected_digest=tiny_c_digest,
        profile="smoke",
        run_id=run_id,
        workers=2,
        resume=True,
        allow_dirty=True,
    )
    assert manifest["resume"] is True and manifest["workers"] == 2
    assert manifest["store_digests"][kept_cell.name] == kept["archive_sha256"]
    assert manifest["store_digests"][other.name] != "partial"
    assert len(manifest["cells"]) == 5
    assert not (run_dir / "stores" / f"{other.name}.sqlite").exists()


def test_run_experiment_refusals(
    repo: Path, tiny_c_digest: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    common: dict[str, Any] = {"protocol_path": PROTOCOL, "profile": "smoke", "run_id": "r"}
    with pytest.raises(ProtocolError, match="registered under"):
        run_experiment(repo, expected_digest="0" * 64, **common)
    original = (repo / PROTOCOL).read_text(encoding="utf-8")
    document = json.loads(original)
    document["software"]["epicormic"] = "0.1.0"
    (repo / PROTOCOL).write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ProtocolError, match="repository pins"):
        run_experiment(repo, expected_digest=protocol_digest(document), **common)
    (repo / PROTOCOL).write_text(original, encoding="utf-8")
    monkeypatch.setattr(
        exp_c, "check_installed", lambda: ["epicormic 0.2.0 is pinned but 9 is installed"]
    )
    with pytest.raises(RunError, match="pinned"):
        run_experiment(repo, expected_digest=tiny_c_digest, **common)
    monkeypatch.setattr(exp_c, "check_installed", list)
    monkeypatch.setattr(exp_c, "git_state", lambda root: {"commit": None, "dirty": None})
    with pytest.raises(RunError, match="clean, committed tree"):
        run_experiment(
            repo, expected_digest=tiny_c_digest, profile="full", run_id="r", protocol_path=PROTOCOL
        )
    with pytest.raises(RunError, match="unknown cells"):
        run_experiment(repo, expected_digest=tiny_c_digest, only_cells=("nope",), **common)


def test_run_experiment_marks_a_failed_run(
    repo: Path, tiny_c_digest: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(job: ChainJob) -> dict[str, Any]:
        raise RunError("cell exploded")

    monkeypatch.setattr(exp_c, "run_cell", boom)
    with pytest.raises(RunError, match="exploded"):
        run_experiment(
            repo,
            protocol_path=PROTOCOL,
            expected_digest=tiny_c_digest,
            profile="smoke",
            run_id="exp-c-smoke-003",
            allow_dirty=True,
            only_cells=("C3-p08-n05-match-l500-q00",),
        )
    manifest = json.loads(
        (repo / EXPERIMENT_DIR / "runs" / "exp-c-smoke-003" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["status"] == "failed"
    assert manifest["only_cells"] == ["C3-p08-n05-match-l500-q00"]
    assert "exp-c-smoke-003" not in (repo / "experiments" / "run_registry.yaml").read_text(
        encoding="utf-8"
    )


def test_tiny_protocol_is_the_real_one_with_a_tiny_grid() -> None:
    document = tiny_c_document()
    real = json.loads(EXP_C_PROTOCOL.read_text(encoding="utf-8"))
    for key in ("provider", "drifts", "outcomes", "run", "software"):
        assert document[key] == real[key]
