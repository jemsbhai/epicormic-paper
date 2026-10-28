"""Write the environment snapshot that every run manifest records.

Usage:
    python scripts/snapshot_environment.py                   # print to standard output
    python scripts/snapshot_environment.py --output environment.json
    python scripts/snapshot_environment.py --require-pins    # exit 1 unless the pins are installed

All logic lives in epicormic_lab.environment; this file only hands over the
arguments.
"""

from __future__ import annotations

import sys

from epicormic_lab.environment import main

if __name__ == "__main__":
    sys.exit(main())
