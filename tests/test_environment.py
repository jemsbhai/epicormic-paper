"""Environment snapshots never guess."""

from __future__ import annotations

import importlib.metadata
import json
import subprocess
from pathlib import Path

import pytest

from epicormic_lab import environment


def test_run_returns_none_when_the_tool_is_absent_or_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_os(*args: object, **kwargs: object) -> None:
        raise OSError("missing")

    monkeypatch.setattr(subprocess, "run", raise_os)
    assert environment._run(["nothing"]) is None

    def timeout(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd="slow", timeout=60)

    monkeypatch.setattr(subprocess, "run", timeout)
    assert environment._run(["slow"]) is None

    class Failed:
        returncode = 1
        stdout = "ignored"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Failed())
    assert environment._run(["failing"]) is None

    class Succeeded:
        returncode = 0
        stdout = " abc123 \n"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Succeeded())
    assert environment._run(["git", "rev-parse", "HEAD"]) == "abc123"


def test_git_state_and_gpu_state(monkeypatch: pytest.MonkeyPatch) -> None:
    answers = {
        "git rev-parse HEAD": "abc123",
        "git status --porcelain": " M file",
        "nvidia-smi": "NVIDIA GeForce RTX 4090 Laptop GPU, 595.79, 16376",
    }

    def fake_run(command: list[str], cwd: Path | None = None) -> str | None:
        key = " ".join(command[:3]) if command[0] == "git" else command[0]
        return answers.get(key)

    monkeypatch.setattr(environment, "_run", fake_run)
    assert environment.git_state(Path(".")) == {"commit": "abc123", "dirty": True}
    assert environment.gpu_state() == {
        "name": "NVIDIA GeForce RTX 4090 Laptop GPU",
        "driver": "595.79",
        "memory_mib": "16376",
    }
    answers["git status --porcelain"] = ""
    assert environment.git_state(Path("."))["dirty"] is False
    answers["nvidia-smi"] = "odd output"
    assert environment.gpu_state() == {"raw": "odd output"}
    del answers["nvidia-smi"]
    assert environment.gpu_state() is None
    del answers["git rev-parse HEAD"]
    del answers["git status --porcelain"]
    assert environment.git_state(Path(".")) == {"commit": None, "dirty": None}


def test_installed_versions_marks_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def version(name: str) -> str:
        if name == "epicormic-lab":
            raise importlib.metadata.PackageNotFoundError(name)
        return "1.0"

    monkeypatch.setattr(importlib.metadata, "version", version)
    assert environment.installed_versions() == {
        "epicormic": "1.0",
        "pollard": "1.0",
        "epicormic-lab": None,
    }


def test_snapshot_writes_the_expected_fields(tmp_path: Path) -> None:
    document = environment.write_snapshot(tmp_path, tmp_path / "out" / "environment.json")
    loaded = json.loads((tmp_path / "out" / "environment.json").read_text(encoding="utf-8"))
    assert loaded == document
    assert set(document) >= {"timestamp", "git", "python_version", "cpu_count", "gpu", "pins"}
    assert document["pins"]["epicormic"]["version"] == "0.2.0"
    assert document["installed"]["epicormic"] == "0.2.0"


def test_total_memory_on_each_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    import os
    import sys

    # Linux path: sysconf (absent on Windows, hence raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(
        os,
        "sysconf",
        lambda name: {"SC_PAGE_SIZE": 4096, "SC_PHYS_PAGES": 10}[name],
        raising=False,
    )
    assert environment.total_memory_bytes() == 40960
    monkeypatch.setattr(
        os, "sysconf", lambda name: (_ for _ in ()).throw(OSError("no")), raising=False
    )
    assert environment.total_memory_bytes() is None
    # macOS path: sysctl
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(environment, "_run", lambda command, cwd=None: "17179869184")
    assert environment.total_memory_bytes() == 17179869184
    # Windows path: powershell, including an unparsable answer and no answer
    monkeypatch.delattr(os, "sysconf", raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(environment, "_run", lambda command, cwd=None: "68719476736")
    assert environment.total_memory_bytes() == 68719476736
    monkeypatch.setattr(environment, "_run", lambda command, cwd=None: "not a number")
    assert environment.total_memory_bytes() is None
    monkeypatch.setattr(environment, "_run", lambda command, cwd=None: None)
    assert environment.total_memory_bytes() is None


def test_installed_distributions_and_pin_status(tmp_path: Path) -> None:
    distributions = environment.installed_distributions()
    assert distributions["epicormic"] == "0.2.0" and distributions["pollard"] == "1.6.0"
    assert list(distributions) == sorted(distributions)
    document = environment.snapshot(tmp_path)
    assert document["pins_ok"] is True
    assert document["distributions"]["epicormic"] == "0.2.0"
    assert "memory_bytes" in document
