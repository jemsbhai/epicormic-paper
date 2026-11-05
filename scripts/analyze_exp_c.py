"""Write the committed EXP-C summary of a run directory to analysis/generated/.

Usage:
    python scripts/analyze_exp_c.py experiments/exp_c_sequential/runs/exp-c-full-001
    python scripts/analyze_exp_c.py RUN_DIR --exp-a-run EXP_A_RUN_DIR

--exp-a-run names the EXP-A run whose A2 chains feed the S-C5 recalibration
grid; without it the grid is reported from the EXP-C quiet chains alone and
the recommendation is withheld. The summary's provenance block says whether
the run can be confirmatory (full profile, completed, clean tree, matching
digests, the complete grid with every planned replication).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from epicormic_lab.exp_a import RunError
from epicormic_lab.exp_c_summary import write_summary

ROOT = Path(__file__).resolve().parent.parent


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--exp-a-run", type=Path, default=None)
    args = parser.parse_args(argv)
    exp_a = None if args.exp_a_run is None else _resolve(args.exp_a_run)
    try:
        print(write_summary(_resolve(args.run_dir), ROOT, exp_a))
    except RunError as error:
        print(f"analysis refused: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
