"""Frozen experiment protocols and their digests.

A protocol is the machine-readable half of a pre-registration: one JSON
object that fixes the design of one experiment (hypotheses, grid, seeds,
scorer set, pinned package versions, analysis plan). It is frozen by the
SHA-256 digest of its canonical serialization, which the logbook plan entry
and every run manifest record. The digest covers the canonical form rather
than the file bytes, so reformatting a file leaves its identity alone and
any change of content moves it.

Canonical form: JSON with keys sorted at every level, no insignificant
whitespace, non-ASCII characters kept as they are, UTF-8 encoded. NaN and
infinity are rejected because JSON has no canonical spelling for them.

Every protocol carries four required keys. ``experiment`` names the
experiment (``EXP-A`` to ``EXP-E``), ``version`` is the date the protocol
version was written (``2026-09-30``, with an optional letter suffix for a
second version on one day), and ``epicormic`` and ``pollard`` must equal the
pinned release versions in :mod:`epicormic_lab.pins`, so the digest commits
to the software under study.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from epicormic_lab.pins import EPICORMIC, POLLARD

EXPERIMENT_PATTERN = re.compile(r"^EXP-[A-E]$")
VERSION_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}[a-z]?$")
REQUIRED_KEYS: tuple[str, ...] = ("experiment", "version", "epicormic", "pollard")


class ProtocolError(ValueError):
    """The protocol is malformed or does not pin the studied releases."""


class ProtocolMismatch(ProtocolError):
    """The protocol on disk no longer matches the digest it was registered under."""

    def __init__(self, path: Path, expected: str, actual: str) -> None:
        super().__init__(f"{path}: expected digest {expected}, found {actual}")
        self.path = path
        self.expected = expected
        self.actual = actual


def canonical_bytes(value: object) -> bytes:
    """Return the canonical UTF-8 JSON serialization of ``value``."""
    try:
        text = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
        return text.encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ProtocolError(f"not canonically serializable: {error}") from error


def protocol_digest(value: object) -> str:
    """Return the SHA-256 hex digest of the canonical serialization of ``value``."""
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


@dataclass(frozen=True)
class Protocol:
    """A loaded protocol: where it came from, what it says, and its digest."""

    path: Path
    data: dict[str, Any]
    digest: str

    @property
    def experiment(self) -> str:
        """The experiment id, ``EXP-A`` to ``EXP-E``."""
        return str(self.data["experiment"])

    @property
    def version(self) -> str:
        """The dated protocol version."""
        return str(self.data["version"])


def validate_protocol(data: object, path: Path | None = None) -> dict[str, Any]:
    """Return ``data`` as a protocol mapping, or raise :class:`ProtocolError`."""
    where = f"{path}: " if path is not None else ""
    if not isinstance(data, dict):
        raise ProtocolError(f"{where}protocol must be a JSON object")
    missing = [key for key in REQUIRED_KEYS if key not in data]
    if missing:
        raise ProtocolError(f"{where}missing required keys: {', '.join(missing)}")
    experiment = data["experiment"]
    if not isinstance(experiment, str) or not EXPERIMENT_PATTERN.match(experiment):
        raise ProtocolError(f"{where}experiment must be EXP-A to EXP-E, got {experiment!r}")
    version = data["version"]
    if not isinstance(version, str) or not VERSION_PATTERN.match(version):
        raise ProtocolError(
            f"{where}version must be a date such as 2026-09-30, with an optional "
            f"letter suffix, got {version!r}"
        )
    for pin in (EPICORMIC, POLLARD):
        if data[pin.name] != pin.version:
            raise ProtocolError(
                f"{where}{pin.name} must be pinned to {pin.version}, got {data[pin.name]!r}"
            )
    return data


def load_protocol(path: Path) -> Protocol:
    """Load, validate, and digest the protocol file at ``path``."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ProtocolError(f"{path}: invalid JSON: {error}") from error
    data = validate_protocol(raw, path)
    return Protocol(path=path, data=data, digest=protocol_digest(data))


def verify_protocol(path: Path, expected: str) -> Protocol:
    """Load ``path`` and raise :class:`ProtocolMismatch` unless its digest is ``expected``."""
    protocol = load_protocol(path)
    if protocol.digest != expected:
        raise ProtocolMismatch(path, expected, protocol.digest)
    return protocol


def main(argv: list[str] | None = None) -> int:
    """Print ``digest  path`` for each protocol, or check one against ``--expect``.

    Exit status: 0 on success, 1 when the digest does not match ``--expect``,
    2 when a protocol cannot be read or is malformed.
    """
    parser = argparse.ArgumentParser(
        prog="freeze_protocol",
        description="Print the SHA-256 digest of a protocol's canonical JSON, or check one.",
    )
    parser.add_argument("protocols", nargs="+", type=Path, metavar="PROTOCOL")
    parser.add_argument(
        "--expect",
        metavar="DIGEST",
        help="exit 1 unless the single given protocol has this digest",
    )
    args = parser.parse_args(argv)
    if args.expect is not None and len(args.protocols) != 1:
        parser.error("--expect takes exactly one protocol")
    try:
        if args.expect is not None:
            protocol = verify_protocol(args.protocols[0], args.expect)
            print(f"{protocol.digest}  {protocol.path}")
            return 0
        for path in args.protocols:
            protocol = load_protocol(path)
            print(f"{protocol.digest}  {protocol.path}")
    except ProtocolMismatch as error:
        print(f"freeze_protocol: {error}", file=sys.stderr)
        return 1
    except (ProtocolError, OSError) as error:
        print(f"freeze_protocol: {error}", file=sys.stderr)
        return 2
    return 0
