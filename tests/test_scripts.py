"""The thin script front-ends load and behave; the logic they call is tested elsewhere."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

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
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    snapshot = _load("snapshot_environment")
    assert snapshot.main([]) == 0
    assert json.loads(capsys.readouterr().out)["pins"]["pollard"]["version"] == "1.6.0"
    out = tmp_path / "environment.json"
    assert snapshot.main(["--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["installed"]["epicormic"] == "0.1.0"


def test_run_and_analyze_scripts_parse_their_arguments() -> None:
    run = _load("run_exp_a")
    with pytest.raises(SystemExit):
        run.main(["--profile", "nightly", "--run-id", "x", "--digest", "0" * 64])
    assert run.main(["--profile", "smoke", "--run-id", "x", "--digest", "0" * 64]) == 1
    analyze = _load("analyze_exp_a")
    with pytest.raises(SystemExit):
        analyze.main([])
