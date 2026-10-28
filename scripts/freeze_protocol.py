"""Print the digest of a protocol file: SHA-256 over its canonical JSON.

Usage:
    python scripts/freeze_protocol.py experiments/exp_a_calibration/protocol.json
    python scripts/freeze_protocol.py PROTOCOL --expect <hex>   # exit 1 on mismatch

The digest goes into the logbook plan entry and into every run manifest.
"""

from __future__ import annotations

import argparse
import sys

from epicormic_lab.protocol import ProtocolError, load_protocol


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("protocol")
    parser.add_argument("--expect", help="fail unless the digest equals this value")
    args = parser.parse_args(argv)
    protocol = load_protocol(args.protocol)
    print(protocol.digest)
    if args.expect:
        try:
            protocol.require_digest(args.expect)
        except ProtocolError as error:
            print(error, file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
