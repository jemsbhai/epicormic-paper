"""The append-only registry writer."""

from __future__ import annotations

from pathlib import Path

import pytest

from epicormic_lab.registry import REGISTRY_FIELDS, RegistryError, append_run, format_entry

ENTRY = {
    "run_id": "exp-a-smoke-001",
    "experiment": "EXP-A",
    "profile": "smoke",
    "front_end": "script",
    "protocol": "experiments/exp_a_calibration/protocol.json",
    "protocol_digest": "ab" * 32,
    "commit": None,
    "epicormic": "0.1.0",
    "pollard": "1.6.0",
    "environment": "experiments/exp_a_calibration/runs/exp-a-smoke-001/environment.json",
    "store_digests": {"A1-p08-n05": "cd" * 32},
    "started": "2026-10-28T12:00:00+00:00",
    "finished": "2026-10-28T12:01:00+00:00",
    "status": "completed",
    "outcome": None,
    "logbook": "2026-10-28 EXP-A planned (mock arm)",
}


def test_format_entry_renders_every_field_in_order() -> None:
    text = format_entry(ENTRY)
    lines = text.splitlines()
    assert lines[0] == '  - run_id: "exp-a-smoke-001"'
    assert "    commit: null" in lines
    assert "    store_digests:" in lines
    assert f'      "A1-p08-n05": "{"cd" * 32}"' in lines
    fields = [line.split(":")[0].strip(" -") for line in lines if not line.startswith("      ")]
    assert fields == list(REGISTRY_FIELDS)


def test_format_entry_handles_empty_and_list_values() -> None:
    entry = {**ENTRY, "store_digests": {}, "outcome": ["a", "b"], "status": True, "commit": 3}
    text = format_entry(entry)
    assert "    store_digests: {}" in text
    assert "    outcome:\n      - \"a\"\n      - \"b\"" in text
    assert "    status: true" in text
    assert "    commit: 3" in text
    assert "    outcome: []" in format_entry({**ENTRY, "outcome": []})


def test_format_entry_rejects_bad_shapes() -> None:
    with pytest.raises(RegistryError, match="lacks fields"):
        format_entry({"run_id": "x"})
    with pytest.raises(RegistryError, match="unknown fields"):
        format_entry({**ENTRY, "extra": 1})
    with pytest.raises(RegistryError, match="unsupported"):
        format_entry({**ENTRY, "commit": 1.5})


def test_append_run_creates_and_extends_the_list(tmp_path: Path) -> None:
    registry = tmp_path / "run_registry.yaml"
    registry.write_text("# header\nruns: []\n", encoding="utf-8")
    append_run(registry, ENTRY)
    text = registry.read_text(encoding="utf-8")
    assert text.startswith("# header\nruns:\n  - run_id:")
    registry.write_text(text.rstrip("\n"), encoding="utf-8")
    append_run(registry, {**ENTRY, "run_id": "exp-a-smoke-002"})
    text = registry.read_text(encoding="utf-8")
    assert text.count("  - run_id:") == 2
    assert '"exp-a-smoke-002"' in text
    registry.write_text("# no list here\n", encoding="utf-8")
    with pytest.raises(RegistryError, match="no runs key"):
        append_run(registry, ENTRY)
