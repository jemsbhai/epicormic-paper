"""EXP-A runner: null windows on the mock provider, one cell at a time.

A cell is one part of the design at one panel size and sample count. For
every replication the runner records one baseline window and K current
windows with disjoint seed sets (``providers.salted``), writes one verdict
per current window through ``epicormic.analyze`` in window order, recomputes
every verdict from the stored observations and fails the run on a mismatch,
and writes a value-free cell summary. The run directory, manifest,
environment snapshot, seeds, registry entry, and the cell loop live in
``run_experiment``; a cell is independent of every other cell, so cells may
run in parallel processes.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from epicormic import Monitor, analyze, observe, recompute_verdict
from pollard import SQLiteStore

from epicormic_lab import __version__ as lab_version
from epicormic_lab.environment import git_state, write_snapshot
from epicormic_lab.pins import EPICORMIC, POLLARD, check_installed
from epicormic_lab.protocol import Cell, Protocol, load_protocol
from epicormic_lab.providers import (
    REPLICATION_STRIDE,
    WINDOW_STRIDE,
    mock_provider,
    salted,
    window_salt,
)
from epicormic_lab.registry import append_run

EXPERIMENT_DIR = Path("experiments") / "exp_a_calibration"
REGISTRY = Path("experiments") / "run_registry.yaml"
CELL_SUMMARY_FORMAT = "epicormic-lab/cell-summary/v1"
MANIFEST_FORMAT = "epicormic-lab/manifest/v1"
LOGBOOK_PLAN_HEADING = "2026-10-28 EXP-A planned (mock arm)"


class RunError(RuntimeError):
    """A run cannot start or cannot be trusted."""


@dataclass(frozen=True)
class CellJob:
    """Everything a worker process needs to run one cell."""

    root: str
    protocol_path: str
    protocol_digest: str
    run_id: str
    profile: str
    run_dir: str
    cell: Cell


def _number(value: Any) -> float | None:
    """Decode a verdict payload number (a decimal string, an int, or None)."""

    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return float(Decimal(str(value)))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def window_id(part: str, replication: int, window_index: int) -> str:
    return f"{part}-r{replication:03d}-w{window_index:02d}"


def monitor_id(part: str, replication: int) -> str:
    return f"{part}-r{replication:03d}"


def verdict_record(
    payload: dict[str, Any], window_index: int, node_id: str | None
) -> dict[str, Any]:
    """Reduce one verdict payload to the fields the calibration analysis reads."""

    pooled: dict[str, Any] = {}
    sequential: dict[str, Any] = {}
    for name, block in payload["scorers"].items():
        p = block["pooled"]
        pooled[name] = {
            "T": _number(p["T"]),
            "p": _number(p["p"]),
            "p_holm": _number(p["p_holm"]),
            "probes": p["probes"],
            "rejected": bool(p["rejected"]),
        }
        seq = block["sequential"]
        cusum, ph, e = seq["cusum"], seq["page_hinkley"], seq["eprocess"]
        sequential[name] = {
            "cusum_alarm": None if cusum is None else bool(cusum["alarm"]),
            "cusum_max": None
            if cusum is None
            else max(_number(cusum["s_plus"]) or 0.0, _number(cusum["s_minus"]) or 0.0),
            "ph_alarm": None if ph is None else bool(ph["alarm"]),
            "ph_excursion": None if ph is None else _number(ph["excursion"]),
            "e_alarm": None if e is None else bool(e["alarm"]),
            "e": None if e is None else _number(e["e"]),
            "e_max": None if e is None else _number(e["max_e"]),
            "e_threshold": None if e is None else _number(e["threshold"]),
            "e_alarm_index": None if e is None else e["alarm_index"],
            "mu0": None if e is None else _number(e["mu0"]),
            "baseline_observations": None if e is None else e["baseline_observations"],
        }
    return {
        "window_index": window_index,
        "window_id": payload["current_window_id"],
        "sequence_index": payload["sequence_index"],
        "node_id": node_id,
        "state": payload["state"],
        "rule_fired": payload["rule_fired"],
        "sample_counts": dict(payload["sample_counts"]),
        "pooled": pooled,
        "sequential": sequential,
    }


def run_cell(job: CellJob) -> dict[str, Any]:
    """Run one cell to completion and write its summary; returns the summary."""

    root = Path(job.root)
    run_dir = Path(job.run_dir)
    protocol = load_protocol(root / job.protocol_path)
    protocol.require_digest(job.protocol_digest)
    cell = job.cell
    panel = protocol.load_panel(root, cell.panel_size)
    config = protocol.analysis_config()
    provider = mock_provider(protocol.document["provider"])
    stores = run_dir / "stores"
    stores.mkdir(parents=True, exist_ok=True)
    store_path = stores / f"{cell.name}.sqlite"
    if store_path.exists():
        store_path.unlink()
    expected_recorded = cell.panel_size * cell.samples
    seconds_observe = seconds_analyze = seconds_recompute = 0.0
    observations = verdicts = 0
    replications: list[dict[str, Any]] = []
    started = time.perf_counter()
    with SQLiteStore(store_path) as store:
        for replication in range(cell.replications):
            window_ids: list[str] = []
            salts: list[int] = []
            for index in range(cell.windows_per_replication):
                wid = window_id(cell.part, replication, index)
                tick = time.perf_counter()
                report = observe(
                    panel,
                    window_id=wid,
                    samples=cell.samples,
                    fn=salted(provider, replication, index, panel.seed_field),
                    store=store,
                )
                seconds_observe += time.perf_counter() - tick
                if report.recorded != expected_recorded or report.refused:
                    raise RunError(
                        f"{cell.name} {wid}: recorded {report.recorded} of {expected_recorded}, "
                        f"refused {report.refused}"
                    )
                observations += report.recorded
                window_ids.append(wid)
                salts.append(window_salt(replication, index))
            baseline = tuple(window_ids[: cell.baseline_windows])
            monitor = Monitor(monitor_id(cell.part, replication), panel.digest, baseline, config)
            records: list[dict[str, Any]] = []
            for index in range(cell.baseline_windows, cell.windows_per_replication):
                tick = time.perf_counter()
                verdict = analyze(store, monitor, window_ids[index])
                seconds_analyze += time.perf_counter() - tick
                tick = time.perf_counter()
                assert verdict.node_id is not None
                _, matched = recompute_verdict(store, monitor, verdict.node_id)
                seconds_recompute += time.perf_counter() - tick
                if not matched:
                    raise RunError(
                        f"{cell.name} {window_ids[index]}: recomputed verdict differs from "
                        f"the recorded one ({verdict.node_id})"
                    )
                verdicts += 1
                records.append(verdict_record(verdict.payload, index, verdict.node_id))
            replications.append(
                {
                    "replication": replication,
                    "monitor_id": monitor.monitor_id,
                    "window_ids": window_ids,
                    "salts": salts,
                    "verdicts": records,
                }
            )
    seconds_total = time.perf_counter() - started
    sidecars = sorted(p.name for p in stores.glob(f"{cell.name}.sqlite-*"))
    summary: dict[str, Any] = {
        "format": CELL_SUMMARY_FORMAT,
        "run_id": job.run_id,
        "experiment": protocol.experiment,
        "profile": job.profile,
        "cell": cell.name,
        **asdict(cell),
        "panel_digest": panel.digest,
        "config_digest": config.digest,
        "protocol_digest": protocol.digest,
        "scorers": list(config.scorers),
        "alpha": float(Decimal(config.alpha)),
        "store": f"stores/{store_path.name}",
        "store_sha256": _sha256(store_path),
        "store_sidecars": sidecars,
        "timing": {
            "seconds_total": seconds_total,
            "seconds_observe": seconds_observe,
            "seconds_analyze": seconds_analyze,
            "seconds_recompute": seconds_recompute,
            "observations": observations,
            "verdicts": verdicts,
            "seconds_per_observation": seconds_observe / observations if observations else None,
            "seconds_per_verdict": seconds_analyze / verdicts if verdicts else None,
        },
        "replications_detail": replications,
    }
    cells_dir = run_dir / "cells"
    cells_dir.mkdir(parents=True, exist_ok=True)
    (cells_dir / f"{cell.name}.json").write_text(
        json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def seed_document(protocol: Protocol, cells: tuple[Cell, ...]) -> dict[str, Any]:
    """The ``seed.json`` content: every source of randomness and the realised ranges."""

    ranges = {}
    for cell in cells:
        last = cell.replications - 1
        ranges[cell.name] = {
            "replications": cell.replications,
            "windows_per_replication": cell.windows_per_replication,
            "first_salt": 0,
            "last_salt": window_salt(max(last, 0), cell.windows_per_replication - 1),
            "seeds_per_window": cell.samples,
        }
    return {
        "provider_seed": protocol.document["provider"]["seed"],
        "analysis_seed": protocol.document["analysis"]["seed"],
        "panel_seed_base": 0,
        "window_salt": {
            "formula": (
                "request_seed + REPLICATION_STRIDE * replication + WINDOW_STRIDE * window_index"
            ),
            "replication_stride": REPLICATION_STRIDE,
            "window_stride": WINDOW_STRIDE,
            "window_index_0": "baseline window",
        },
        "cells": ranges,
    }


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _write_json(path: Path, document: dict[str, Any]) -> None:
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_experiment(
    root: Path,
    *,
    protocol_path: Path,
    expected_digest: str,
    profile: str,
    run_id: str,
    workers: int = 1,
    resume: bool = False,
    allow_dirty: bool = False,
    front_end: str = "script",
    only_cells: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Run the protocol's cells for ``profile`` and write the run directory.

    ``expected_digest`` is the protocol digest the run was registered under
    (the logbook plan entry). The full profile refuses a dirty tree unless
    ``allow_dirty`` is set, and the flag is recorded in the manifest. With
    ``resume`` the cells that already have a summary are kept and every other
    cell is rerun from its first replication. ``only_cells`` restricts the
    run to the named cells, which is for instrumentation only and is also
    recorded.
    """

    protocol = load_protocol(root / protocol_path)
    protocol.require_digest(expected_digest)
    problems = check_installed()
    if problems:
        raise RunError("; ".join(problems))
    git = git_state(root)
    if profile == "full" and git["dirty"] is not False and not allow_dirty:
        raise RunError("a full run needs a clean, committed tree (or --allow-dirty, recorded)")
    panels = protocol.verify_panels(root)
    cells = protocol.cells(profile)
    if only_cells:
        unknown = sorted(set(only_cells) - {cell.name for cell in cells})
        if unknown:
            raise RunError(f"unknown cells: {unknown}")
        cells = tuple(cell for cell in cells if cell.name in only_cells)
    run_dir = root / EXPERIMENT_DIR / "runs" / run_id
    if run_dir.exists() and not resume:
        raise RunError(f"{run_dir} exists; choose a new run id or pass --resume")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "protocol.frozen.json").write_bytes((root / protocol_path).read_bytes())
    write_snapshot(root, run_dir / "environment.json")
    _write_json(run_dir / "seed.json", seed_document(protocol, cells))
    started = _now()
    manifest: dict[str, Any] = {
        "format": MANIFEST_FORMAT,
        "run_id": run_id,
        "experiment": protocol.experiment,
        "arm": protocol.arm,
        "profile": profile,
        "front_end": front_end,
        "protocol": {
            "path": protocol_path.as_posix(),
            "version": protocol.version,
            "digest": protocol.digest,
        },
        "config_digest": protocol.analysis_config().digest,
        "panels": panels,
        "git": git,
        "allow_dirty": allow_dirty,
        "resume": resume,
        "only_cells": list(only_cells),
        "workers": workers,
        "epicormic_lab": lab_version,
        "pins": {EPICORMIC.name: EPICORMIC.version, POLLARD.name: POLLARD.version},
        "started": started,
        "finished": None,
        "status": "running",
        "cells": [],
        "store_digests": {},
    }
    _write_json(run_dir / "manifest.json", manifest)

    summaries: dict[str, dict[str, Any]] = {}
    pending: list[CellJob] = []
    for cell in cells:
        summary_path = run_dir / "cells" / f"{cell.name}.json"
        if resume and summary_path.exists():
            summaries[cell.name] = json.loads(summary_path.read_text(encoding="utf-8"))
            continue
        pending.append(
            CellJob(
                root=str(root),
                protocol_path=protocol_path.as_posix(),
                protocol_digest=protocol.digest,
                run_id=run_id,
                profile=profile,
                run_dir=str(run_dir),
                cell=cell,
            )
        )
    try:
        if workers > 1 and len(pending) > 1:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                for summary in pool.map(run_cell, pending):
                    summaries[summary["cell"]] = summary
        else:
            for job in pending:
                summary = run_cell(job)
                summaries[summary["cell"]] = summary
    except Exception:
        manifest["finished"] = _now()
        manifest["status"] = "failed"
        _write_json(run_dir / "manifest.json", manifest)
        raise
    manifest["cells"] = [
        {
            "cell": cell.name,
            "summary": f"cells/{cell.name}.json",
            "store": summaries[cell.name]["store"],
            "timing": summaries[cell.name]["timing"],
        }
        for cell in cells
    ]
    manifest["store_digests"] = {cell.name: summaries[cell.name]["store_sha256"] for cell in cells}
    manifest["finished"] = _now()
    manifest["status"] = "completed"
    _write_json(run_dir / "manifest.json", manifest)
    append_run(
        root / REGISTRY,
        {
            "run_id": run_id,
            "experiment": protocol.experiment,
            "profile": profile,
            "front_end": front_end,
            "protocol": protocol_path.as_posix(),
            "protocol_digest": protocol.digest,
            "commit": git["commit"],
            "epicormic": EPICORMIC.version,
            "pollard": POLLARD.version,
            "environment": (EXPERIMENT_DIR / "runs" / run_id / "environment.json").as_posix(),
            "store_digests": manifest["store_digests"],
            "started": started,
            "finished": manifest["finished"],
            "status": "completed",
            "outcome": None,
            "logbook": LOGBOOK_PLAN_HEADING,
        },
    )
    return manifest
