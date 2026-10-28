"""The append-only run registry, ``experiments/run_registry.yaml``.

The registry is a YAML document with one key, ``runs``, holding one mapping
per run. This module appends a mapping without a YAML dependency: the
values it writes are strings, integers, booleans, nulls, lists of strings,
and flat mappings of strings, and the emitter quotes every string, so the
file stays valid YAML and readable by any YAML parser. Nothing is ever
rewritten: an existing entry is never touched, and the only edit to earlier
text is turning the empty ``runs: []`` of a fresh registry into ``runs:``
the first time an entry is appended.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

REGISTRY_FIELDS = (
    "run_id",
    "experiment",
    "profile",
    "front_end",
    "protocol",
    "protocol_digest",
    "commit",
    "epicormic",
    "pollard",
    "environment",
    "store_digests",
    "started",
    "finished",
    "status",
    "outcome",
    "logbook",
)


class RegistryError(ValueError):
    """The registry file or an entry is not in the expected shape."""


def _scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    raise RegistryError(f"unsupported registry value {value!r}")


def format_entry(entry: Mapping[str, Any]) -> str:
    """Render one run as a YAML list item, fields in registry order."""

    missing = [field for field in REGISTRY_FIELDS if field not in entry]
    if missing:
        raise RegistryError(f"registry entry lacks fields: {missing}")
    unknown = sorted(set(entry) - set(REGISTRY_FIELDS))
    if unknown:
        raise RegistryError(f"registry entry has unknown fields: {unknown}")
    lines: list[str] = []
    for index, field in enumerate(REGISTRY_FIELDS):
        prefix = "  - " if index == 0 else "    "
        value = entry[field]
        if isinstance(value, Mapping):
            if not value:
                lines.append(f"{prefix}{field}: {{}}")
                continue
            lines.append(f"{prefix}{field}:")
            for key in sorted(value):
                quoted = json.dumps(str(key), ensure_ascii=False)
                lines.append(f"      {quoted}: {_scalar(value[key])}")
        elif isinstance(value, Sequence) and not isinstance(value, str):
            if not value:
                lines.append(f"{prefix}{field}: []")
                continue
            lines.append(f"{prefix}{field}:")
            lines.extend(f"      - {_scalar(item)}" for item in value)
        else:
            lines.append(f"{prefix}{field}: {_scalar(value)}")
    return "\n".join(lines) + "\n"


def append_run(registry_path: Path, entry: Mapping[str, Any]) -> None:
    """Append ``entry`` to the registry, creating the ``runs:`` list on first use."""

    text = registry_path.read_text(encoding="utf-8")
    rendered = format_entry(entry)
    stripped = text.rstrip()
    if stripped.endswith("runs: []"):
        text = stripped[: -len("runs: []")] + "runs:\n"
    elif "\nruns:" not in "\n" + stripped:
        raise RegistryError(f"{registry_path} has no runs key")
    elif not text.endswith("\n"):
        text += "\n"
    registry_path.write_text(text + rendered, encoding="utf-8")
