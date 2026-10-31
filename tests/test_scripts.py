"""The thin script front-ends load and behave; the logic they call is tested elsewhere."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from .conftest import REAL_PROTOCOL, REPO
from .test_protocol import FROZEN_DIGEST


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_freeze_protocol_prints_and_checks_the_digest(capsys: pytest.CaptureFixture[str]) -> None:
    freeze = _load("freeze_protocol")
    assert freeze.main([str(REAL_PROTOCOL)]) == 0
    assert capsys.readouterr().out.strip() == FROZEN_DIGEST
    assert freeze.main([str(REAL_PROTOCOL), "--expect", FROZEN_DIGEST]) == 0
    assert freeze.main([str(REAL_PROTOCOL), "--expect", "0" * 64]) == 1
    assert "registered under" in capsys.readouterr().err


def test_snapshot_environment_prints_or_writes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = _load("snapshot_environment")
    assert snapshot.main([]) == 0
    assert json.loads(capsys.readouterr().out)["pins"]["pollard"]["version"] == "1.6.0"
    out = tmp_path / "environment.json"
    assert snapshot.main(["--out", str(out), "--require-pins"]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["installed"]["epicormic"] == "0.2.0"
    capsys.readouterr()
    monkeypatch.setattr(snapshot, "snapshot", lambda root: {"pins_ok": False})
    assert snapshot.main(["--require-pins"]) == 1
    assert "not the installed ones" in capsys.readouterr().err


def test_run_and_analyze_scripts_parse_their_arguments() -> None:
    run = _load("run_exp_a")
    with pytest.raises(SystemExit):
        run.main(["--profile", "nightly", "--run-id", "x", "--digest", "0" * 64])
    assert run.main(["--profile", "smoke", "--run-id", "x", "--digest", "0" * 64]) == 1
    analyze = _load("analyze_exp_a")
    with pytest.raises(SystemExit):
        analyze.main([])


def test_pilot_exp_c_runs_a_tiny_setting_and_rejects_unknown_kinds(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    pilot = _load("pilot_exp_c")
    out = tmp_path / "pilot.json"
    assert pilot.main(["--out", str(out), "--kinds", "latency"]) == 1
    assert "unknown drift kinds" in capsys.readouterr().err
    argv = [
        "--out",
        str(out),
        "--panel",
        "data/panels/mock-08-v1.json",
        "--samples",
        "5",
        "--windows",
        "3",
        "--change",
        "2",
        "--reps",
        "1",
        "--permutations",
        "200",
        "--kinds",
        "refusal",
        "--levels",
        "1",
    ]
    assert pilot.main(argv) == 0
    document = json.loads(out.read_text(encoding="utf-8"))
    assert document["purpose"] == "sizing only, not evidence"
    assert document["kinds"] == {"refusal": "refusal"} and len(document["chains"]) == 1
    chain = document["chains"][0]
    assert chain["kind"] == "refusal" and chain["level"] == "1" and chain["change_window"] == 2
    assert chain["detectors"]["refusal"]["pooled"]["delay"] == 1
    assert chain["effects"]["refusal"]["T_post_mean"] == pytest.approx(1.0)

    class SerialPool:
        """Stands in for the process pool: a module loaded from a path cannot be pickled."""

        def __init__(self, max_workers: int) -> None:
            self.max_workers = max_workers

        def __enter__(self) -> SerialPool:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def map(self, fn: Any, items: list[Any]) -> list[Any]:
            return [fn(item) for item in items]

    monkeypatch.setattr(pilot, "ProcessPoolExecutor", SerialPool)
    assert pilot.main([*argv, "--workers", "2"]) == 0
    assert len(json.loads(out.read_text(encoding="utf-8"))["chains"]) == 1
