"""Frozen experiment protocols: loading, canonical digests, cells, and panel checks.

A protocol is the machine-readable twin of a pre-registration. Its digest is
SHA-256 over the canonical JSON serialization (keys sorted, no insignificant
whitespace, ``ensure_ascii`` false, UTF-8), recorded in the logbook plan
entry and in every run manifest. ``Protocol.require_digest`` is how a run
refuses to start when the file on disk no longer matches the digest it was
registered under.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from epicormic import AnalysisConfig, Panel, load_panel

PROTOCOL_FORMAT = "epicormic-lab/protocol/v1"
PROFILES = ("smoke", "full")


class ProtocolError(ValueError):
    """A protocol file is malformed, or the repository does not match it."""


def canonical_json(document: Any) -> bytes:
    """Return the canonical UTF-8 JSON bytes whose SHA-256 is the protocol digest."""

    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def protocol_digest(document: Any) -> str:
    """SHA-256 of the canonical JSON of ``document``."""

    return hashlib.sha256(canonical_json(document)).hexdigest()


@dataclass(frozen=True)
class Cell:
    """One cell of the design grid: a part at one panel size and sample count."""

    part: str
    panel_size: int
    samples: int
    baseline_windows: int
    current_windows: int
    replications: int

    @property
    def name(self) -> str:
        return f"{self.part}-p{self.panel_size:02d}-n{self.samples:02d}"

    @property
    def windows_per_replication(self) -> int:
        return self.baseline_windows + self.current_windows


@dataclass(frozen=True)
class Protocol:
    """A loaded protocol: its path, its document, and its digest."""

    path: Path
    document: dict[str, Any]
    digest: str

    @property
    def experiment(self) -> str:
        return str(self.document["experiment"])

    @property
    def version(self) -> str:
        return str(self.document["version"])

    @property
    def arm(self) -> str:
        return str(self.document["arm"])

    def require_digest(self, expected: str) -> None:
        """Raise unless the file's digest equals the digest it was registered under."""

        if self.digest != expected:
            raise ProtocolError(
                f"{self.path} has digest {self.digest}, but the run was registered under "
                f"{expected}; a changed protocol is a new dated version, never an edit"
            )

    def cells(self, profile: str) -> tuple[Cell, ...]:
        """Enumerate the cells of every part in protocol order for ``profile``."""

        if profile not in PROFILES:
            raise ProtocolError(f"profile must be one of {PROFILES}, got {profile!r}")
        cells: list[Cell] = []
        for part, spec in self.document["parts"].items():
            for panel_size in spec["panel_sizes"]:
                for samples in spec["samples_per_probe"]:
                    cells.append(
                        Cell(
                            part=str(part),
                            panel_size=int(panel_size),
                            samples=int(samples),
                            baseline_windows=int(spec["baseline_windows"]),
                            current_windows=int(spec["current_windows"]),
                            replications=int(spec["replications"][profile]),
                        )
                    )
        return tuple(cells)

    def panel_entry(self, panel_size: int) -> dict[str, str]:
        """The ``{"path", "digest"}`` entry of the panel used at ``panel_size``."""

        try:
            entry = self.document["panels"][str(panel_size)]
        except KeyError as error:
            raise ProtocolError(f"protocol names no panel of size {panel_size}") from error
        return {"path": str(entry["path"]), "digest": str(entry["digest"])}

    def load_panel(self, root: Path, panel_size: int) -> Panel:
        """Load the panel for ``panel_size`` from ``root`` and check its digest."""

        entry = self.panel_entry(panel_size)
        panel = load_panel(root / entry["path"])
        if panel.digest != entry["digest"]:
            raise ProtocolError(
                f"{entry['path']} has panel digest {panel.digest}, protocol expects "
                f"{entry['digest']}"
            )
        if len(panel.probes) != panel_size:
            raise ProtocolError(
                f"{entry['path']} has {len(panel.probes)} probes, protocol expects {panel_size}"
            )
        return panel

    def verify_panels(self, root: Path) -> dict[str, str]:
        """Load every panel the protocol names and return ``{path: digest}``."""

        return {
            self.panel_entry(int(size))["path"]: self.load_panel(root, int(size)).digest
            for size in self.document["panels"]
        }

    def analysis_document(self) -> dict[str, Any]:
        """The ``epicormic/config/v1`` document of the protocol's analysis block.

        The protocol writes the three sequential detectors under one
        ``sequential`` key, following the constructor sketch in section 5.5
        of the epicormic plan; the config document format itself carries
        ``cusum``, ``page_hinkley`` and ``eprocess`` at the top level. The
        translation is a lossless move of those three keys and nothing else;
        the config digest that results is recorded in every run manifest.
        """

        block = dict(self.document["analysis"])
        sequential = block.pop("sequential", {})
        for key, value in sequential.items():
            if key in block:
                raise ProtocolError(f"analysis block names {key!r} twice")
            block[key] = value
        return block

    def analysis_config(self) -> AnalysisConfig:
        """The validated analysis configuration."""

        return AnalysisConfig.from_document(self.analysis_document())


def load_protocol(path: str | Path) -> Protocol:
    """Load a protocol file, check its format, and compute its digest."""

    file = Path(path)
    try:
        document = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ProtocolError(f"{file} is not valid JSON: {error}") from error
    if not isinstance(document, dict) or document.get("format") != PROTOCOL_FORMAT:
        raise ProtocolError(f"{file} is not a {PROTOCOL_FORMAT} document")
    for key in ("experiment", "version", "arm", "panels", "analysis", "parts", "provider"):
        if key not in document:
            raise ProtocolError(f"{file} lacks the {key!r} key")
    return Protocol(path=file, document=document, digest=protocol_digest(document))
