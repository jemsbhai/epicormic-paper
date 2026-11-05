"""EXP-C runner: change-point chains on the mock provider, one cell at a time.

A cell is one part of the design at one panel size, sample count, drift
kind, level and quiet length (protocol ``run.cell``). For every replication
the runner records one chain: the baseline window, the quiet windows
answered by the null mock and the post-change windows answered by the
drifted mock of the cell's kind and level, with the window salt of EXP-A so
that every window is a fresh draw and cells at one geometry share their
baseline and quiet windows replication by replication (common random
numbers, protocol ``run.common_random_numbers``). The current windows are
analysed in order by ``epicormic_lab.chains``, every verdict is recomputed
from the stored observations, and the chain is reduced to its first alarms
and delays by ``first_alarms``. When the cell is complete its store is
zipped, the archive's digest recorded, and the uncompressed store removed
(protocol ``run.archive``); the cell summary, with the per-window verdict
records of every chain, is written gzip-compressed (``artifacts``). The run
directory, manifest, environment snapshot, seeds, registry entry and the
cell loop live in ``run_experiment`` and mirror the EXP-A runner.
"""

from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from epicormic import Monitor
from pollard import SQLiteStore

from epicormic_lab import __version__ as lab_version
from epicormic_lab.chains import ChainError, analyze_chain, first_alarms, observe_chain
from epicormic_lab.environment import git_state, write_snapshot
from epicormic_lab.exp_a import MANIFEST_FORMAT, REGISTRY, RunError, window_id
from epicormic_lab.pins import EPICORMIC, POLLARD, check_installed
from epicormic_lab.protocol import Protocol, load_protocol
from epicormic_lab.providers import (
    DRIFT_KINDS,
    MIXTURE_TAG,
    REPLICATION_STRIDE,
    WINDOW_STRIDE,
    drift_level,
    drifted_provider,
    mock_provider,
    window_salt,
)
from epicormic_lab.registry import append_run

EXPERIMENT_DIR = Path("experiments") / "exp_c_sequential"
CELL_SUMMARY_FORMAT = "epicormic-lab/chain-cell-summary/v1"
LOGBOOK_PLAN_HEADING = "2026-10-29 EXP-C planned (mock arm)"
# protocol run.cell_order: C3, C1 by kind in protocol order then increasing level, C2
PART_ORDER = ("C3", "C1", "C2")


@dataclass(frozen=True)
class ChainCell:
    """One cell of the EXP-C grid: a part at one geometry, kind, level and quiet length."""

    part: str
    panel_size: int
    samples: int
    kind: str
    level: str
    baseline_windows: int
    pre_change_windows: int
    post_change_windows: int
    replications: int

    @property
    def level_thousandths(self) -> int:
        return int(Decimal(self.level) * 1000)

    @property
    def name(self) -> str:
        return (
            f"{self.part}-p{self.panel_size:02d}-n{self.samples:02d}-{self.kind}"
            f"-l{self.level_thousandths:03d}-q{self.pre_change_windows:02d}"
        )

    @property
    def current_windows(self) -> int:
        return self.pre_change_windows + self.post_change_windows

    @property
    def windows_per_replication(self) -> int:
        return self.baseline_windows + self.current_windows

    @property
    def change_window(self) -> int:
        """The first drifted window, 1-based over the current windows."""

        return self.pre_change_windows + 1


@dataclass(frozen=True)
class ChainJob:
    """Everything a worker process needs to run one cell."""

    root: str
    protocol_path: str
    protocol_digest: str
    run_id: str
    profile: str
    run_dir: str
    cell: ChainCell


def chain_cells(protocol: Protocol, profile: str) -> tuple[ChainCell, ...]:
    """Enumerate the cells of every part in protocol order for ``profile``."""

    if profile not in ("smoke", "full"):
        raise RunError(f"profile must be smoke or full, got {profile!r}")
    kinds_known = set(DRIFT_KINDS)
    cells: list[ChainCell] = []
    for part, spec in protocol.document["parts"].items():
        unknown = sorted(set(spec["kinds"]) - kinds_known)
        if unknown:
            raise RunError(f"part {part} names unknown drift kinds {unknown}")
        for level in spec["levels"]:
            drift_level(level)
        for panel_size in spec["panel_sizes"]:
            for samples in spec["samples_per_probe"]:
                for quiet in spec["pre_change_windows"]:
                    for kind in spec["kinds"]:
                        for level in spec["levels"]:
                            cells.append(
                                ChainCell(
                                    part=str(part),
                                    panel_size=int(panel_size),
                                    samples=int(samples),
                                    kind=str(kind),
                                    level=str(level),
                                    baseline_windows=int(spec["baseline_windows"]),
                                    pre_change_windows=int(quiet),
                                    post_change_windows=int(spec["post_change_windows"]),
                                    replications=int(spec["replications"][profile]),
                                )
                            )
    names = [cell.name for cell in cells]
    if len(set(names)) != len(names):
        raise RunError("the protocol enumerates two cells with one name")
    return tuple(cells)


def execution_order(cells: tuple[ChainCell, ...], protocol: Protocol) -> tuple[ChainCell, ...]:
    """The cells in the order the protocol runs them: C3, C1 by kind then level, C2.

    Within a part the order is the protocol's kind order, then increasing
    level, then quiet length, panel size and N, so that the long C1 cells
    start early and the order is the same on every machine.
    """

    parts = list(protocol.document["parts"])
    kinds = list(DRIFT_KINDS)

    def rank(cell: ChainCell) -> tuple[int, int, int, float, int, int, int]:
        part_rank = PART_ORDER.index(cell.part) if cell.part in PART_ORDER else len(PART_ORDER)
        return (
            part_rank,
            parts.index(cell.part),
            kinds.index(cell.kind),
            drift_level(cell.level),
            cell.pre_change_windows,
            cell.panel_size,
            cell.samples,
        )

    return tuple(sorted(cells, key=rank))


def monitor_id(cell: ChainCell, replication: int) -> str:
    return f"{cell.name}-r{replication:03d}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def summary_path(run_dir: Path, cell_name: str) -> Path:
    return run_dir / "cells" / f"{cell_name}.json.gz"


def write_cell_summary(path: Path, summary: dict[str, Any]) -> None:
    """Write a cell summary as gzip-compressed compact JSON with a fixed header time."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(summary, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    with path.open("wb") as handle, gzip.GzipFile(
        filename="", mode="wb", fileobj=handle, mtime=0
    ) as archive:
        archive.write(payload)


def read_cell_summary(path: Path) -> dict[str, Any]:
    """Read a cell summary written by ``write_cell_summary`` (or a plain ``.json``)."""

    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            document = json.load(handle)
    else:
        document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise RunError(f"{path} is not a cell summary")
    return document


def _remove_store(stores: Path, cell_name: str) -> None:
    for path in stores.glob(f"{cell_name}.sqlite*"):
        path.unlink()
    archive = stores / f"{cell_name}.zip"
    if archive.exists():
        archive.unlink()


def archive_store(stores: Path, cell_name: str) -> dict[str, Any]:
    """Zip a cell's store with its sidecars, remove the originals, return the digests."""

    store_path = stores / f"{cell_name}.sqlite"
    sidecars = sorted(p.name for p in stores.glob(f"{cell_name}.sqlite-*"))
    archive = stores / f"{cell_name}.zip"
    store_sha256 = _sha256(store_path)
    store_bytes = store_path.stat().st_size
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.write(store_path, arcname=store_path.name)
        for name in sidecars:
            zf.write(stores / name, arcname=name)
    archive_sha256 = _sha256(archive)
    archive_bytes = archive.stat().st_size
    store_path.unlink()
    for name in sidecars:
        (stores / name).unlink()
    return {
        "store": f"stores/{store_path.name}",
        "store_sha256": store_sha256,
        "store_bytes": store_bytes,
        "store_sidecars": sidecars,
        "archive": f"stores/{archive.name}",
        "archive_sha256": archive_sha256,
        "archive_bytes": archive_bytes,
    }


def run_cell(job: ChainJob) -> dict[str, Any]:
    """Run one cell to completion, archive its store and write its summary."""

    root = Path(job.root)
    run_dir = Path(job.run_dir)
    protocol = load_protocol(root / job.protocol_path)
    protocol.require_digest(job.protocol_digest)
    cell = job.cell
    panel = protocol.load_panel(root, cell.panel_size)
    config = protocol.analysis_config()
    spec = protocol.document["provider"]
    null = mock_provider(spec)
    drifted = drifted_provider(spec, cell.kind, cell.level)
    stores = run_dir / "stores"
    stores.mkdir(parents=True, exist_ok=True)
    _remove_store(stores, cell.name)
    store_path = stores / f"{cell.name}.sqlite"
    quiet = cell.baseline_windows + cell.pre_change_windows
    providers = [null] * quiet + [drifted] * cell.post_change_windows
    seconds_observe = seconds_analyze = 0.0
    observations = verdicts = 0
    chains: list[dict[str, Any]] = []
    started = time.perf_counter()
    with SQLiteStore(store_path) as store:
        for replication in range(cell.replications):
            windows = cell.windows_per_replication
            ids = [window_id(cell.part, replication, i) for i in range(windows)]
            tick = time.perf_counter()
            try:
                recorded = observe_chain(
                    store,
                    panel,
                    samples=cell.samples,
                    window_ids=ids,
                    providers=providers,
                    replication=replication,
                )
            except ChainError as error:
                raise RunError(f"{cell.name} replication {replication}: {error}") from error
            seconds_observe += time.perf_counter() - tick
            observations += recorded
            monitor = Monitor(
                monitor_id(cell, replication),
                panel.digest,
                tuple(ids[: cell.baseline_windows]),
                config,
            )
            tick = time.perf_counter()
            try:
                records = analyze_chain(
                    store, monitor, ids[cell.baseline_windows :], recompute=True
                )
            except ChainError as error:
                raise RunError(f"{cell.name} replication {replication}: {error}") from error
            seconds_analyze += time.perf_counter() - tick
            verdicts += len(records)
            summary = first_alarms(records, cell.change_window, config.scorers)
            summary.update(
                {"kind": cell.kind, "level": cell.level, "replication": replication}
            )
            chains.append(
                {
                    "replication": replication,
                    "monitor_id": monitor.monitor_id,
                    "window_ids": ids,
                    "salts": [window_salt(replication, i) for i in range(len(ids))],
                    "change_window": cell.change_window,
                    "verdicts": records,
                    "first_alarms": summary,
                }
            )
    tick = time.perf_counter()
    archive = archive_store(stores, cell.name)
    seconds_archive = time.perf_counter() - tick
    seconds_total = time.perf_counter() - started
    document: dict[str, Any] = {
        "format": CELL_SUMMARY_FORMAT,
        "run_id": job.run_id,
        "experiment": protocol.experiment,
        "profile": job.profile,
        "cell": cell.name,
        **asdict(cell),
        "primary_scorer": DRIFT_KINDS[cell.kind],
        "change_window": cell.change_window,
        "current_windows": cell.current_windows,
        "windows_per_replication": cell.windows_per_replication,
        "panel_digest": panel.digest,
        "config_digest": config.digest,
        "protocol_digest": protocol.digest,
        "scorers": list(config.scorers),
        "alpha": float(Decimal(config.alpha)),
        **archive,
        "timing": {
            "seconds_total": seconds_total,
            "seconds_observe": seconds_observe,
            "seconds_analyze_and_recompute": seconds_analyze,
            "seconds_archive": seconds_archive,
            "observations": observations,
            "verdicts": verdicts,
            "chains": len(chains),
            "seconds_per_observation": seconds_observe / observations if observations else None,
            "seconds_per_verdict": seconds_analyze / verdicts if verdicts else None,
            "seconds_per_chain": seconds_total / len(chains) if chains else None,
        },
        "chains": chains,
    }
    write_cell_summary(summary_path(run_dir, cell.name), document)
    return document


def seed_document(protocol: Protocol, cells: tuple[ChainCell, ...]) -> dict[str, Any]:
    """The ``seed.json`` content: every source of randomness and the realised ranges."""

    ranges = {}
    for cell in cells:
        last = max(cell.replications - 1, 0)
        ranges[cell.name] = {
            "kind": cell.kind,
            "level": cell.level,
            "replications": cell.replications,
            "windows_per_replication": cell.windows_per_replication,
            "change_window": cell.change_window,
            "first_salt": 0,
            "last_salt": window_salt(last, cell.windows_per_replication - 1),
            "seeds_per_window": cell.samples,
        }
    return {
        "provider_seed": protocol.document["provider"]["seed"],
        "drifted_provider_seed": protocol.document["provider"]["seed"],
        "analysis_seed": protocol.document["analysis"]["seed"],
        "panel_seed_base": 0,
        "window_salt": {
            "formula": (
                "request_seed + REPLICATION_STRIDE * replication + WINDOW_STRIDE * window_index"
            ),
            "replication_stride": REPLICATION_STRIDE,
            "window_stride": WINDOW_STRIDE,
            "window_index_0": "baseline window",
            "change": "the drifted provider answers window indices >= baseline_windows + "
            "pre_change_windows; the change window is pre_change_windows + 1 over the "
            "current windows",
        },
        "mixture": {
            "tag": MIXTURE_TAG.decode("ascii"),
            "routing": "first 8 bytes of SHA-256(tag + canonical JSON of the salted request) "
            "as a unit fraction, compared with the level; no seed",
        },
        "cells": ranges,
    }


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _write_json(path: Path, document: dict[str, Any]) -> None:
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def finished_summary(run_dir: Path, cell: ChainCell, run_id: str) -> dict[str, Any] | None:
    """The summary of a completed cell, or ``None`` when it must be (re)run.

    A cell counts as finished only when its summary reads, belongs to this
    run and cell, and its archived store exists with the recorded digest.
    """

    path = summary_path(run_dir, cell.name)
    if not path.exists():
        return None
    try:
        document = read_cell_summary(path)
    except (OSError, ValueError, RunError):
        return None
    if (
        document.get("format") != CELL_SUMMARY_FORMAT
        or document.get("run_id") != run_id
        or document.get("cell") != cell.name
        or document.get("archive") != f"stores/{cell.name}.zip"
    ):
        return None
    archive = run_dir / str(document["archive"])
    if not archive.is_file() or _sha256(archive) != document.get("archive_sha256"):
        return None
    return document


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
    ``resume`` the cells that already have a summary and an intact archive
    are kept and every other cell is rerun from its first replication.
    ``only_cells`` restricts the run to the named cells, which is for
    instrumentation only and is also recorded.
    """

    protocol = load_protocol(root / protocol_path)
    protocol.require_digest(expected_digest)
    protocol.require_software()
    problems = check_installed()
    if problems:
        raise RunError("; ".join(problems))
    git = git_state(root)
    if profile == "full" and git["dirty"] is not False and not allow_dirty:
        raise RunError("a full run needs a clean, committed tree (or --allow-dirty, recorded)")
    panels = protocol.verify_panels(root)
    cells = execution_order(chain_cells(protocol, profile), protocol)
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
        "cell_order": [cell.name for cell in cells],
        "started": started,
        "finished": None,
        "status": "running",
        "cells": [],
        "store_digests": {},
    }
    _write_json(run_dir / "manifest.json", manifest)

    summaries: dict[str, dict[str, Any]] = {}
    pending: list[ChainJob] = []
    for cell in cells:
        kept = finished_summary(run_dir, cell, run_id) if resume else None
        if kept is not None:
            summaries[cell.name] = kept
            continue
        pending.append(
            ChainJob(
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
            "part": cell.part,
            "kind": cell.kind,
            "level": cell.level,
            "samples": cell.samples,
            "pre_change_windows": cell.pre_change_windows,
            "replications": cell.replications,
            "summary": f"cells/{cell.name}.json.gz",
            "archive": summaries[cell.name]["archive"],
            "archive_sha256": summaries[cell.name]["archive_sha256"],
            "timing": summaries[cell.name]["timing"],
        }
        for cell in cells
    ]
    manifest["store_digests"] = {
        cell.name: summaries[cell.name]["archive_sha256"] for cell in cells
    }
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


def project_full_profile(
    protocol: Protocol, manifest: dict[str, Any], workers: int
) -> dict[str, Any]:
    """Project the full-profile wall-clock from a smoke manifest (protocol ``run.sizing``).

    Each full cell's time is its smoke seconds per chain times its full
    replication count; the cells are dispatched in execution order to the
    first free worker, as the runner's process pool does, and the
    projection is the makespan. Cells absent from the manifest (a run with
    ``only_cells``) are reported and make the projection partial.
    """

    if workers < 1:
        raise RunError("workers must be at least 1")
    timings = {entry["cell"]: entry["timing"] for entry in manifest.get("cells", [])}
    full = execution_order(chain_cells(protocol, "full"), protocol)
    finish = [0.0] * workers
    per_cell: list[dict[str, Any]] = []
    missing: list[str] = []
    cpu_seconds = 0.0
    for cell in full:
        timing = timings.get(cell.name)
        if timing is None or not timing.get("seconds_per_chain"):
            missing.append(cell.name)
            continue
        seconds = float(timing["seconds_per_chain"]) * cell.replications
        cpu_seconds += seconds
        worker = min(range(workers), key=lambda w: finish[w])
        start = finish[worker]
        finish[worker] = start + seconds
        per_cell.append(
            {
                "cell": cell.name,
                "replications": cell.replications,
                "seconds_per_chain": float(timing["seconds_per_chain"]),
                "seconds": seconds,
                "worker": worker,
                "start": start,
                "finish": finish[worker],
            }
        )
    makespan = max(finish) if per_cell else 0.0
    return {
        "workers": workers,
        "cells_projected": len(per_cell),
        "cells_missing": missing,
        "cpu_hours": cpu_seconds / 3600,
        "makespan_hours": makespan / 3600,
        "longest_cell_hours": max((c["seconds"] for c in per_cell), default=0.0) / 3600,
        "within_12_hours": bool(per_cell) and not missing and makespan <= 12 * 3600,
        "per_cell": per_cell,
    }
