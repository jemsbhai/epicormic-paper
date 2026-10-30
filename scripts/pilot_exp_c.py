"""EXP-C sizing pilot: realised effect per scorer and detection delay per detector on the mock.

Usage:
    python scripts/pilot_exp_c.py --out experiments/exp_c_sequential/pilot/pilot-seed7.json
    python scripts/pilot_exp_c.py --seed 7 --reps 10 --workers 2 --out pilot.json

A pilot is for sizing and is never evidence: it runs on its own provider
seed (7 by default; the registered experiment uses another), with fewer
permutations than the protocol (the sequential detectors do not depend on
the permutation count; the per-window pooled test's resolution does), and
its numbers enter the pre-registration as the basis of the hypotheses, the
delay bounds, and the replication counts. Each chain is one baseline window
and K current windows of one panel at N samples per probe; the null mock
answers the windows before the change and the drifted mock answers the
change window and every window after it. The output is one JSON document
with the settings and, per chain, the first-alarm summary of
``epicormic_lab.chains.first_alarms``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from epicormic import AnalysisConfig, Monitor, load_panel
from pollard import MemoryStore

from epicormic_lab.chains import analyze_chain, chain_window_ids, first_alarms, observe_chain
from epicormic_lab.providers import DRIFT_KINDS, drifted_provider, mock_provider

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PANEL = Path("data") / "panels" / "canary-24-v1.json"
SCORERS = (
    "normalized_match",
    "exact_match",
    "tool_call_set_jaccard",
    "refusal",
    "truncated",
    "output_chars",
    "output_tokens",
)
DEFAULT_LEVELS = ("0.05", "0.1", "0.2", "0.3", "0.5")


def run_setting(args: dict[str, Any]) -> list[dict[str, Any]]:
    """Run every chain of one (kind, level) setting and return their summaries."""

    panel = load_panel(ROOT / args["panel"])
    config = AnalysisConfig(scorers=SCORERS, permutations=args["permutations"])
    spec = {
        "kind": "epicormic.mock.MockProvider",
        "seed": args["seed"],
        "match_rate": "0.9",
        "drift": None,
    }
    null = mock_provider(spec)
    drifted = drifted_provider(spec, args["kind"], args["level"])
    windows, change = args["windows"], args["change"]
    summaries: list[dict[str, Any]] = []
    started = time.perf_counter()
    for replication in range(args["reps"]):
        store = MemoryStore()
        prefix = f"{args['kind']}-l{args['level']}-r{replication:03d}"
        ids = chain_window_ids(prefix, windows)
        current = [drifted if index >= change else null for index in range(1, windows + 1)]
        providers = [null, *current]
        observe_chain(
            store,
            panel,
            samples=args["samples"],
            window_ids=ids,
            providers=providers,
            replication=replication,
        )
        monitor = Monitor(prefix, panel.digest, (ids[0],), config)
        records = analyze_chain(store, monitor, ids[1:])
        summary = first_alarms(records, change, SCORERS)
        summary.update({"kind": args["kind"], "level": args["level"], "replication": replication})
        summaries.append(summary)
    seconds = time.perf_counter() - started
    label = f"{args['kind']:10} {args['level']:>5}"
    print(f"{label} {args['reps']} chains in {seconds:7.1f} s", flush=True)
    return summaries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=7, help="mock provider seed of the pilot")
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--windows", type=int, default=28, help="current windows per chain")
    parser.add_argument("--change", type=int, default=15, help="first drifted window, 1-based")
    parser.add_argument("--reps", type=int, default=10)
    parser.add_argument("--permutations", type=int, default=200)
    parser.add_argument("--kinds", nargs="*", default=list(DRIFT_KINDS))
    parser.add_argument("--levels", nargs="*", default=list(DEFAULT_LEVELS))
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args(argv)
    unknown = [kind for kind in args.kinds if kind not in DRIFT_KINDS]
    if unknown:
        print(f"unknown drift kinds: {unknown}", file=sys.stderr)
        return 1
    settings = [
        {
            "kind": kind,
            "level": level,
            "seed": args.seed,
            "panel": args.panel.as_posix(),
            "samples": args.samples,
            "windows": args.windows,
            "change": args.change,
            "reps": args.reps,
            "permutations": args.permutations,
        }
        for kind in args.kinds
        for level in args.levels
    ]
    chains: list[dict[str, Any]] = []
    if args.workers > 1:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for summaries in pool.map(run_setting, settings):
                chains.extend(summaries)
    else:
        for setting in settings:
            chains.extend(run_setting(setting))
    document = {
        "format": "epicormic-lab/exp-c-pilot/v1",
        "purpose": "sizing only, not evidence",
        "panel": args.panel.as_posix(),
        "seed": args.seed,
        "samples": args.samples,
        "windows": args.windows,
        "change": args.change,
        "reps": args.reps,
        "permutations": args.permutations,
        "scorers": list(SCORERS),
        "kinds": {kind: DRIFT_KINDS[kind] for kind in args.kinds},
        "levels": list(args.levels),
        "chains": chains,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.out} with {len(chains)} chains")
    return 0


if __name__ == "__main__":
    sys.exit(main())
