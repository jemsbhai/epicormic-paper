"""Write an environment snapshot (commit, dirty flag, interpreter, platform, GPU, pins).

Usage:
    python scripts/snapshot_environment.py [--out environment.json]

Without --out the snapshot is printed. Runs write their own snapshot into the
run directory; this script is for reporting an environment before a run.
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
    args = parser.parse_args(argv)
    if args.out:
        write_snapshot(ROOT, args.out)
        print(args.out)
    else:
        print(json.dumps(snapshot(ROOT), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
