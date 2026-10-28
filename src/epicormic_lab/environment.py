"""Environment snapshots for run manifests.

Every run writes an ``environment.json`` next to its frozen protocol: when
it started, which commit of this repository ran and whether the tree was
clean, which interpreter and platform, how much memory and how many CPUs,
which GPUs and driver, every installed distribution with its version, and
whether the pinned releases of epicormic and pollard are what is installed.
Nothing here identifies the machine beyond its hardware class: no hostname,
no user name, no file system paths.

External commands (``git``, ``nvidia-smi``) are reached through a runner
callable so that tests can supply both their presence and their absence.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil

from epicormic_lab._version import __version__
from epicormic_lab.pins import PINS, Pin, check_installed

Runner = Callable[[list[str], "Path | None"], tuple[int, str]]


def run_command(args: list[str], cwd: Path | None = None) -> tuple[int, str]:
    """Run ``args`` and return its exit status and standard output.

    A missing executable is reported as status 127 with empty output rather
    than as an exception, so a machine without ``nvidia-smi`` still gets a
    snapshot.
    """
    try:
        completed = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return 127, ""
    return completed.returncode, completed.stdout


def git_identity(repo_root: Path, run: Runner = run_command) -> dict[str, Any]:
    """Return the HEAD commit of ``repo_root`` and whether its working tree is dirty.

    ``available`` is False when ``repo_root`` is not inside a git repository or
    git is not installed; ``dirty`` is None when the status could not be read.
    """
    status, head = run(["git", "rev-parse", "HEAD"], repo_root)
    if status != 0:
        return {"available": False, "commit": None, "dirty": None}
    status, porcelain = run(["git", "status", "--porcelain"], repo_root)
    dirty = bool(porcelain.strip()) if status == 0 else None
    return {"available": True, "commit": head.strip(), "dirty": dirty}


def gpu_identity(run: Runner = run_command) -> list[dict[str, str]]:
    """Return name, driver version, and memory of every GPU that nvidia-smi reports."""
    status, output = run(
        ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
        None,
    )
    if status != 0:
        return []
    gpus: list[dict[str, str]] = []
    for line in output.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) >= 3:
            gpus.append({"name": parts[0], "driver": parts[1], "memory": parts[2]})
    return gpus


def installed_distributions() -> dict[str, str]:
    """Return every installed distribution, lower-cased name to version, sorted by name."""
    found: dict[str, str] = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.name
        if name:
            found[name.lower()] = distribution.version
    return dict(sorted(found.items()))


def pin_status(pin: Pin) -> dict[str, str | None]:
    """Return the pinned and the installed version of one pin; installed is None if absent."""
    try:
        installed: str | None = pin.installed_version()
    except importlib.metadata.PackageNotFoundError:
        installed = None
    return {"pinned": pin.version, "installed": installed}


def snapshot_environment(repo_root: Path, run: Runner = run_command) -> dict[str, Any]:
    """Return the environment snapshot for a run started now in ``repo_root``."""
    memory = psutil.virtual_memory()
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "epicormic_lab": __version__,
        "git": git_identity(repo_root, run),
        "pins": {pin.name: pin_status(pin) for pin in PINS},
        "pins_ok": check_installed() == [],
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        },
        "cpu_count": psutil.cpu_count(logical=True),
        "memory_total_gb": round(memory.total / 1024**3, 1),
        "gpus": gpu_identity(run),
        "packages": installed_distributions(),
    }


def write_snapshot(path: Path, snapshot: dict[str, Any]) -> None:
    """Write ``snapshot`` to ``path`` as sorted, indented JSON with a final newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Print the snapshot or write it with ``--output``; check the pins.

    Exit status: 0 on success, 1 when ``--require-pins`` is set and a pinned
    release is missing or at another version.
    """
    parser = argparse.ArgumentParser(
        prog="snapshot_environment",
        description="Write the environment snapshot that every run manifest records.",
    )
    parser.add_argument(
        "--repo", type=Path, default=Path.cwd(), help="repository root (default: current directory)"
    )
    parser.add_argument("--output", type=Path, help="write JSON here instead of standard output")
    parser.add_argument(
        "--require-pins",
        action="store_true",
        help="exit 1 unless the pinned releases of epicormic and pollard are installed",
    )
    args = parser.parse_args(argv)
    snapshot = snapshot_environment(args.repo)
    if args.output is not None:
        write_snapshot(args.output, snapshot)
    else:
        print(json.dumps(snapshot, indent=2, sort_keys=True))
    if args.require_pins and not snapshot["pins_ok"]:
        for problem in check_installed():
            print(f"snapshot_environment: {problem}", file=sys.stderr)
        return 1
    return 0
