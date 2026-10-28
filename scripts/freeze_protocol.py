"""Print the SHA-256 digest of a protocol's canonical JSON, or check one.

Usage:
    python scripts/freeze_protocol.py experiments/exp_a_calibration/protocol.json
    python scripts/freeze_protocol.py PROTOCOL --expect DIGEST

The digest goes into the logbook plan entry and the run registry; a run
refuses to start when the protocol on disk no longer matches it. All logic
lives in epicormic_lab.protocol; this file only hands over the arguments.
"""

from __future__ import annotations

import sys

from epicormic_lab.protocol import main

if __name__ == "__main__":
    sys.exit(main())
