"""Environment snapshots: what a run ran on, written to ``environment.json``.

The snapshot records the repository commit and whether the tree was clean,
the interpreter and platform, the CPU count and physical memory, the GPU and
driver when ``nvidia-smi`` answers, the installed versions of the studied
packages with their pinned release digests, every installed distribution,
whether the pins are satisfied, and the time. Every field that comes from a
subprocess is ``None`` when the tool is absent, never a guess.
"""

from __future__ import annotations

import datetime as dt
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from epicormic_lab.pins import PINS, check_installed

TRACKED_DISTRIBUTIONS = ("epicormic", "pollard", "epicormic-lab")


def _run(command: list[str], cwd: Path | None = None) -> str | None:
    """Return the stripped stdout of ``command``, or ``None`` when it cannot run."""

    try:
        completed = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, check=False, timeout=60
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def git_state(root: Path) -> dict[str, Any]:
    """The commit of ``root`` and whether its working tree has uncommitted changes."""

    commit = _run(["git", "rev-parse", "HEAD"], cwd=root)
    status = _run(["git", "status", "--porcelain"], cwd=root)
    return {
        "commit": commit,
        "dirty": None if status is None else bool(status),
    }


def gpu_state() -> dict[str, Any] | None:
    """The first GPU's name, driver version, and memory as ``nvidia-smi`` reports them."""

    output = _run(
        [
            "nvidia-smi",
            "--query-gpu=name,driver_version,memory.total",
            "--format=csv,noheader,nounits",
        ]
    )
    if not output:
        return None
    fields = [field.strip() for field in output.splitlines()[0].split(",")]
    if len(fields) != 3:
        return {"raw": output}
    return {"name": fields[0], "driver": fields[1], "memory_mib": fields[2]}


def installed_versions() -> dict[str, str | None]:
    """Installed versions of the tracked distributions, ``None`` when not installed."""

    versions: dict[str, str | None] = {}
    for name in TRACKED_DISTRIBUTIONS:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def installed_distributions() -> dict[str, str]:
    """Every installed distribution and its version, sorted by name."""

    found: dict[str, str] = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata["Name"]
        if name:
            found[str(name)] = str(distribution.version)
    return dict(sorted(found.items()))


def total_memory_bytes() -> int | None:
    """Physical memory of the host from the standard library and the platform's own tool."""

    if hasattr(os, "sysconf") and sys.platform != "darwin":
        try:
            return int(os.sysconf("SC_PAGE_SIZE")) * int(os.sysconf("SC_PHYS_PAGES"))
        except (ValueError, OSError):
            return None
    if sys.platform == "darwin":
        output = _run(["sysctl", "-n", "hw.memsize"])
    else:
        output = _run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory",
            ]
        )
    try:
        return int(output) if output else None
    except ValueError:
        return None


def snapshot(root: Path) -> dict[str, Any]:
    """Collect the environment snapshot for a run rooted at ``root``."""

    return {
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "git": git_state(root),
        "python": sys.version,
        "python_version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "cpu_count": os.cpu_count(),
        "memory_bytes": total_memory_bytes(),
        "gpu": gpu_state(),
        "installed": installed_versions(),
        "distributions": installed_distributions(),
        "pins_ok": check_installed() == [],
        "pins": {
            pin.name: {
                "version": pin.version,
                "tag": pin.tag,
                "commit": pin.commit,
                "wheel_sha256": pin.wheel_sha256,
                "sdist_sha256": pin.sdist_sha256,
            }
            for pin in PINS
        },
    }


def write_snapshot(root: Path, path: Path) -> dict[str, Any]:
    """Write the snapshot of ``root`` to ``path`` as indented JSON and return it."""

    document = snapshot(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return document
