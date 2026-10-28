"""Experiment code for the epicormic paper.

Scripts under scripts/ and notebooks under notebooks/ are thin front-ends
over this package: they load a frozen protocol, run it through the same
functions, and write the same run manifests. The experiment logic lives here
and nowhere else, so a script run and a notebook run of one protocol are the
same computation.
"""

from __future__ import annotations

from epicormic_lab._version import __version__
from epicormic_lab.environment import snapshot_environment, write_snapshot
from epicormic_lab.pins import EPICORMIC, PINS, POLLARD, Pin, check_installed
from epicormic_lab.protocol import (
    Protocol,
    ProtocolError,
    ProtocolMismatch,
    canonical_bytes,
    load_protocol,
    protocol_digest,
    validate_protocol,
    verify_protocol,
)

__all__ = [
    "EPICORMIC",
    "PINS",
    "POLLARD",
    "Pin",
    "Protocol",
    "ProtocolError",
    "ProtocolMismatch",
    "__version__",
    "canonical_bytes",
    "check_installed",
    "load_protocol",
    "protocol_digest",
    "snapshot_environment",
    "validate_protocol",
    "verify_protocol",
    "write_snapshot",
]
