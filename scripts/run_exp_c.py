"""Run EXP-C (mock arm) from the frozen protocol.

Usage:
    python scripts/run_exp_c.py --profile smoke --run-id exp-c-smoke-001 --digest <hex> --workers 4
    python scripts/run_exp_c.py --profile full --run-id exp-c-full-001 --digest <hex> --workers 8

--digest is the protocol digest from the logbook plan entry; the run refuses
to start when the protocol file no longer matches it. A full run needs a
clean tree. --resume keeps cells whose summary and archived store are
intact and reruns the rest from their first replication. --cells limits the
run to named cells (instrumentation only, recorded in the manifest). Each
cell's store is zipped under runs/<run_id>/stores/ when the cell completes
and the uncompressed store is removed; the cell summaries are written
gzip-compressed under runs/<run_id>/cells/. After a smoke run the script
prints the projected wall-clock of the full profile at --workers, which the
sizing rule of the pre-registration (section 4) reads. After the run,
scripts/analyze_exp_c.py writes the committed summary.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from epicormic_lab.exp_a import RunError
from epicormic_lab.exp_c import EXPERIMENT_DIR, project_full_profile, run_experiment
from epicormic_lab.protocol import ProtocolError, load_protocol

ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--profile", choices=("smoke", "full"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--digest", required=True, help="protocol digest from the logbook entry")
    parser.add_argument(
        "--protocol",
        type=Path,
        default=EXPERIMENT_DIR / "protocol.json",
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
        per_verdict = timing["seconds_per_verdict"]
        print(
            f"{cell['cell']}: {timing['chains']} chains, {timing['verdicts']} verdicts, "
            f"{timing['seconds_total']:.1f} s"
            + (f", {per_verdict:.2f} s per verdict" if per_verdict is not None else "")
        )
    if args.profile == "smoke":
        protocol = load_protocol(ROOT / args.protocol)
        projection = project_full_profile(protocol, manifest, args.workers)
        missing = projection["cells_missing"]
        print(
            f"projected full profile at {projection['workers']} workers: "
            f"{projection['makespan_hours']:.1f} h wall-clock (makespan), "
            f"{projection['cpu_hours']:.1f} CPU-hours, longest cell "
            f"{projection['longest_cell_hours']:.1f} h; within 12 hours: "
            f"{'yes' if projection['within_12_hours'] else 'no'}"
            + (f"; cells not timed: {missing}" if missing else "")
        )
    print(f"{manifest['run_id']} {manifest['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
