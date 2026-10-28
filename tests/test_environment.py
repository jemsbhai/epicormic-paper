"""Environment snapshots: external commands, git and GPU identity, pins, and the command."""

from __future__ import annotations

import importlib.metadata
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

import epicormic_lab
from epicormic_lab.environment import (
    git_identity,
    gpu_identity,
    installed_distributions,
    main,
    pin_status,
    run_command,
    snapshot_environment,
    write_snapshot,
)
from epicormic_lab.pins import EPICORMIC, POLLARD

HEX_40 = re.compile(r"^[0-9a-f]{40}$")
NVIDIA_SMI_OUTPUT = "NVIDIA GeForce RTX 4090 Laptop GPU, 581.15, 16376 MiB\nmalformed line\n"


def make_runner(
    git_head: tuple[int, str] = (0, "0123456789abcdef0123456789abcdef01234567\n"),
    git_status: tuple[int, str] = (0, ""),
    nvidia: tuple[int, str] = (0, NVIDIA_SMI_OUTPUT),
) -> Any:
    """Return a runner that answers git and nvidia-smi from canned results."""
    calls: list[tuple[list[str], Path | None]] = []

    def run(args: list[str], cwd: Path | None) -> tuple[int, str]:
        calls.append((args, cwd))
        if args[:2] == ["git", "rev-parse"]:
            return git_head
        if args[:2] == ["git", "status"]:
            return git_status
        if args[0] == "nvidia-smi":
            return nvidia
        raise AssertionError(f"unexpected command {args}")

    run.calls = calls  # type: ignore[attr-defined]
    return run


def test_run_command_returns_status_and_stdout() -> None:
    status, out = run_command([sys.executable, "-c", "print('hello')"])
    assert status == 0
    assert out.strip() == "hello"


def test_run_command_reports_a_missing_executable_as_127() -> None:
    assert run_command(["epicormic-lab-no-such-command-7f3a"]) == (127, "")


def test_git_identity_clean_tree(tmp_path: Path) -> None:
    run = make_runner()
    assert git_identity(tmp_path, run) == {
        "available": True,
        "commit": "0123456789abcdef0123456789abcdef01234567",
        "dirty": False,
    }
    assert run.calls[0] == (["git", "rev-parse", "HEAD"], tmp_path)


def test_git_identity_dirty_tree(tmp_path: Path) -> None:
    run = make_runner(git_status=(0, " M README.md\n?? new.txt\n"))
    assert git_identity(tmp_path, run)["dirty"] is True


def test_git_identity_unknown_status_when_status_fails(tmp_path: Path) -> None:
    run = make_runner(git_status=(1, ""))
    assert git_identity(tmp_path, run)["dirty"] is None


def test_git_identity_unavailable_outside_a_repository(tmp_path: Path) -> None:
    run = make_runner(git_head=(128, ""))
    assert git_identity(tmp_path, run) == {"available": False, "commit": None, "dirty": None}


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_git_identity_against_a_real_repository(tmp_path: Path) -> None:
    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "lab@example.invalid")
    git("config", "user.name", "lab")
    (tmp_path / "file.txt").write_text("one\n", encoding="utf-8")
    git("add", "file.txt")
    git("commit", "-q", "-m", "one")

    clean = git_identity(tmp_path)
    assert clean["available"] is True
    assert isinstance(clean["commit"], str)
    assert HEX_40.match(clean["commit"])
    assert clean["dirty"] is False

    (tmp_path / "file.txt").write_text("two\n", encoding="utf-8")
    assert git_identity(tmp_path)["dirty"] is True


def test_gpu_identity_parses_nvidia_smi_rows_and_skips_malformed_ones() -> None:
    assert gpu_identity(make_runner()) == [
        {"name": "NVIDIA GeForce RTX 4090 Laptop GPU", "driver": "581.15", "memory": "16376 MiB"}
    ]


def test_gpu_identity_is_empty_without_nvidia_smi() -> None:
    assert gpu_identity(make_runner(nvidia=(127, ""))) == []


def test_installed_distributions_lists_the_pinned_releases_sorted() -> None:
    packages = installed_distributions()
    assert packages["epicormic"] == EPICORMIC.version
    assert packages["pollard"] == POLLARD.version
    assert "pytest" in packages
    assert list(packages) == sorted(packages)


def test_installed_distributions_skips_a_distribution_without_a_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Nameless:
        name = ""
        version = "0"

    class Named:
        name = "Example-Dist"
        version = "1.2"

    monkeypatch.setattr(importlib.metadata, "distributions", lambda: [Nameless(), Named()])
    assert installed_distributions() == {"example-dist": "1.2"}


def test_pin_status_reports_installed_and_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    assert pin_status(EPICORMIC) == {"pinned": EPICORMIC.version, "installed": EPICORMIC.version}

    def missing(name: str) -> str:
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, "version", missing)
    assert pin_status(POLLARD) == {"pinned": POLLARD.version, "installed": None}


def test_snapshot_environment_has_every_field(tmp_path: Path) -> None:
    run = make_runner()
    snapshot = snapshot_environment(tmp_path, run)
    assert snapshot["timestamp"].endswith("+00:00")
    assert snapshot["epicormic_lab"] == epicormic_lab.__version__
    assert snapshot["git"]["commit"] == "0123456789abcdef0123456789abcdef01234567"
    assert snapshot["pins"] == {
        "epicormic": {"pinned": EPICORMIC.version, "installed": EPICORMIC.version},
        "pollard": {"pinned": POLLARD.version, "installed": POLLARD.version},
    }
    assert snapshot["pins_ok"] is True
    assert snapshot["python"]["version"] == sys.version.split()[0]
    assert set(snapshot["platform"]) == {"system", "release", "version", "machine", "processor"}
    assert snapshot["cpu_count"] >= 1
    assert snapshot["memory_total_gb"] > 0
    assert snapshot["gpus"][0]["driver"] == "581.15"
    assert snapshot["packages"]["epicormic"] == EPICORMIC.version
    assert "hostname" not in json.dumps(snapshot)
    json.dumps(snapshot)


def test_snapshot_environment_records_missing_pins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def missing(name: str) -> str:
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, "version", missing)
    snapshot = snapshot_environment(tmp_path, make_runner())
    assert snapshot["pins_ok"] is False
    assert snapshot["pins"]["epicormic"]["installed"] is None


def test_write_snapshot_creates_parents_and_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "runs" / "exp-a-smoke-001" / "environment.json"
    write_snapshot(path, {"b": 1, "a": {"z": None}})
    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert text.index('"a"') < text.index('"b"')
    assert json.loads(text) == {"a": {"z": None}, "b": 1}


def test_main_prints_json_by_default(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--repo", str(tmp_path)]) == 0
    snapshot = json.loads(capsys.readouterr().out)
    assert snapshot["git"]["available"] in (True, False)
    assert snapshot["packages"]["epicormic"] == EPICORMIC.version


def test_main_writes_the_output_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "environment.json"
    assert main(["--repo", str(tmp_path), "--output", str(output)]) == 0
    assert capsys.readouterr().out == ""
    assert json.loads(output.read_text(encoding="utf-8"))["pins_ok"] is True


def test_main_require_pins_passes_in_a_pinned_environment(tmp_path: Path) -> None:
    output = tmp_path / "e.json"
    assert main(["--repo", str(tmp_path), "--output", str(output), "--require-pins"]) == 0


def test_main_require_pins_fails_when_a_pin_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def missing(name: str) -> str:
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, "version", missing)
    output = tmp_path / "e.json"
    assert main(["--repo", str(tmp_path), "--output", str(output), "--require-pins"]) == 1
    err = capsys.readouterr().err
    assert "snapshot_environment: epicormic 0.1.0 is pinned but not installed" in err
    assert "snapshot_environment: pollard 1.6.0 is pinned but not installed" in err
