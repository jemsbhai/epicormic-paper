"""Shared fixtures: a temporary repository copy with a tiny EXP-A protocol."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from epicormic_lab.protocol import protocol_digest

REPO = Path(__file__).resolve().parent.parent
REAL_PROTOCOL = REPO / "experiments" / "exp_a_calibration" / "protocol.2026-10-28-r2.json"
FIRST_PROTOCOL = REPO / "experiments" / "exp_a_calibration" / "protocol.json"

TINY_PARTS = {
    "A1": {
        "question": "tiny",
        "panel_sizes": [8],
        "samples_per_probe": [5],
        "baseline_windows": 1,
        "current_windows": 1,
        "replications": {"smoke": 2, "full": 3},
    },
    "A2": {
        "question": "tiny",
        "panel_sizes": [8],
        "samples_per_probe": [5],
        "baseline_windows": 1,
        "current_windows": 3,
        "replications": {"smoke": 2, "full": 2},
    },
    "A3": {
        "question": "tiny",
        "panel_sizes": [8],
        "samples_per_probe": [3],
        "baseline_windows": 1,
        "current_windows": 1,
        "replications": {"smoke": 2, "full": 2},
    },
}


def tiny_document() -> dict[str, object]:
    document = json.loads(REAL_PROTOCOL.read_text(encoding="utf-8"))
    document["parts"] = TINY_PARTS
    document["analysis"]["permutations"] = 200
    document["version"] = "tiny"
    return document


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository copy with the real panels, a tiny protocol, and an empty registry."""

    root = tmp_path / "repo"
    (root / "data").mkdir(parents=True)
    shutil.copytree(REPO / "data" / "panels", root / "data" / "panels")
    experiment = root / "experiments" / "exp_a_calibration"
    experiment.mkdir(parents=True)
    (experiment / "protocol.json").write_text(
        json.dumps(tiny_document(), indent=2) + "\n", encoding="utf-8"
    )
    registry = root / "experiments" / "run_registry.yaml"
    registry.write_text("# registry\nruns: []\n", encoding="utf-8")
    return root


@pytest.fixture
def tiny_digest() -> str:
    return protocol_digest(tiny_document())
