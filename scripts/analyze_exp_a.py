"""Write the committed EXP-A summary of a run directory to analysis/generated/.

Usage:
    python scripts/analyze_exp_a.py experiments/exp_a_calibration/runs/exp-a-full-001
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from epicormic_lab.analysis import write_summary

ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args(argv)
    run_dir = args.run_dir if args.run_dir.is_absolute() else ROOT / args.run_dir
    print(write_summary(run_dir, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
