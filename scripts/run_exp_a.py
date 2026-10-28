"""Run EXP-A (mock arm) from the frozen protocol.

Usage:
    python scripts/run_exp_a.py --profile smoke --run-id exp-a-smoke-001 --digest <hex>
    python scripts/run_exp_a.py --profile full --run-id exp-a-full-001 --digest <hex> --workers 8

--digest is the protocol digest from the logbook plan entry; the run refuses
to start when the protocol file no longer matches it. A full run needs a
clean tree. --resume keeps finished cells and reruns the rest from their
first replication. --cells limits the run to named cells (instrumentation
only, recorded in the manifest). After the run, scripts/analyze_exp_a.py
writes the committed summary.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from epicormic_lab.exp_a import EXPERIMENT_DIR, RunError, run_experiment
from epicormic_lab.protocol import ProtocolError

ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--profile", choices=("smoke", "full"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--digest", required=True, help="protocol digest from the logbook entry")
    parser.add_argument(
        "--protocol",
        type=Path,
        default=EXPERIMENT_DIR / "protocol.2026-10-28-r2.json",
        help="protocol path relative to the repository root",
    )
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--cells", nargs="*", default=[])
    args = parser.parse_args(argv)
    try:
        manifest = run_experiment(
            ROOT,
            protocol_path=args.protocol,
            expected_digest=args.digest,
            profile=args.profile,
            run_id=args.run_id,
            workers=args.workers,
            resume=args.resume,
            allow_dirty=args.allow_dirty,
            only_cells=tuple(args.cells),
        )
    except (RunError, ProtocolError) as error:
        print(f"run refused: {error}", file=sys.stderr)
        return 1
    for cell in manifest["cells"]:
        timing = cell["timing"]
        print(
            f"{cell['cell']}: {timing['observations']} observations, "
            f"{timing['verdicts']} verdicts, {timing['seconds_total']:.1f} s"
        )
    print(f"{manifest['run_id']} {manifest['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
