"""Write an environment snapshot (commit, dirty flag, interpreter, platform, GPU, pins).

Usage:
    python scripts/snapshot_environment.py [--out environment.json] [--require-pins]

Without --out the snapshot is printed. Runs write their own snapshot into the
run directory; this script is for reporting an environment before a run.
With --require-pins the exit status is 1 unless the pinned releases are the
installed ones.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from epicormic_lab.environment import snapshot, write_snapshot

ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, help="write the snapshot here instead of printing it")
    parser.add_argument(
        "--require-pins", action="store_true", help="exit 1 unless the pins are installed"
    )
    args = parser.parse_args(argv)
    document = write_snapshot(ROOT, args.out) if args.out else snapshot(ROOT)
    print(args.out if args.out else json.dumps(document, indent=2, sort_keys=True))
    if args.require_pins and not document["pins_ok"]:
        print("pinned releases are not the installed ones", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
