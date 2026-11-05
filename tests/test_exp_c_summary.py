"""The EXP-C summary: on a tiny real run, and on a synthetic full grid with known answers."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from epicormic.stats.sequential import cusum, page_hinkley

from epicormic_lab.chains import first_alarms
from epicormic_lab.exp_a import RunError
from epicormic_lab.exp_c import (
    CELL_SUMMARY_FORMAT,
    EXPERIMENT_DIR,
    ChainCell,
    chain_cells,
    read_cell_summary,
    run_experiment,
    summary_path,
    write_cell_summary,
)
from epicormic_lab.exp_c_summary import (
    SUMMARY_FORMAT,
    default_check,
    detection_block,
    detection_quantile,
    export,
    h_c1,
    h_c2,
    s_c5,
    shared_window_check,
    summarize_cell,
    summarize_exp_c,
    write_summary,
)
from epicormic_lab.protocol import load_protocol, protocol_digest
from epicormic_lab.stats import binomial_cdf

from .conftest import EXP_C_PROTOCOL, REPO, tiny_c_document

PROTOCOL = Path("experiments") / "exp_c_sequential" / "protocol.json"
SCORERS = ("normalized_match", "refusal", "output_chars")
PRIMARY = {"match": "normalized_match", "refusal": "refusal", "truncation": "refusal",
           "tool_swap": "normalized_match", "length": "output_chars"}


# --- a tiny real run -------------------------------------------------------------


@pytest.fixture(scope="module")
def tiny_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    root = tmp_path_factory.mktemp("summary") / "repo"
    (root / "data").mkdir(parents=True)
    shutil.copytree(REPO / "data" / "panels", root / "data" / "panels")
    (root / EXPERIMENT_DIR).mkdir(parents=True)
    (root / PROTOCOL).write_text(json.dumps(tiny_c_document(), indent=2) + "\n", encoding="utf-8")
    (root / "experiments" / "run_registry.yaml").write_text("runs: []\n", encoding="utf-8")
    run_experiment(
        root,
        protocol_path=PROTOCOL,
        expected_digest=protocol_digest(tiny_c_document()),
        profile="smoke",
        run_id="exp-c-smoke-009",
        allow_dirty=True,
    )
    return root, root / EXPERIMENT_DIR / "runs" / "exp-c-smoke-009"


def test_tiny_run_summary_structure(tiny_run: tuple[Path, Path]) -> None:
    root, run_dir = tiny_run
    summary = summarize_exp_c(run_dir)
    assert summary["format"] == SUMMARY_FORMAT and summary["run_ids"] == ["exp-c-smoke-009"]
    assert summary["profile"] == "smoke" and summary["provenance"]["confirmatory"] is False
    assert summary["provenance"]["complete_grid"] is True
    assert summary["provenance"]["protocol_digest_matches_manifest"] is True
    assert summary["provenance"]["cell_digests_match"] is True
    check = summary["shared_window_check"]
    assert check["p08-n05"]["reference"] == "C3-p08-n05-match-l500-q04"
    assert check["p08-n05"]["agree"] is True and check["p08-n05"]["chains_compared"] == 4
    assert check["p08-n10"]["chains_compared"] == 0
    cells = {cell["cell"]: cell for cell in summary["cells"]}
    refusal = cells["C1-p08-n05-refusal-l500-q02"]
    assert refusal["state"]["drift"]["within"]["1"]["count"] == 2
    assert refusal["detectors"]["refusal"]["pooled"]["all_chains"]["total"] == 2
    assert refusal["effects"]["refusal"]["T_post"]["n"] == 2
    assert set(summary["s_c3"]) == {"p08-n05-q02", "p08-n05-q04", "p08-n10-q02"}
    assert summary["s_c3"]["p08-n05-q02"]["note"].startswith("prefix of the chains with 4")
    assert summary["s_c3"]["p08-n05-q04"]["note"] is None
    assert summary["s_c3"]["p08-n05-q04"]["state"]["sticky_before_change"]["total"] == 2
    assert summary["h_c1"]["family_size"] == 0 and summary["h_c1"]["cells"] == []
    assert summary["h_c2"]["computed"] is False and "missing cells" in summary["h_c2"]["reason"]
    assert summary["s_c4"] == {"0.1": {}, "0.2": {}}
    s_c5 = summary["s_c5"]
    assert s_c5["default_check"]["chains_passed"] == 10 == s_c5["default_check"]["chains_checked"]
    assert s_c5["cusum"]["recommended"] is None and s_c5["exp_a"] is None
    assert s_c5["cusum"]["recommendation_withheld"] == "no EXP-A full run supplied"
    assert summary["export"]["bound_days"] is None
    path = write_summary(run_dir, root)
    assert path == root / "analysis" / "generated" / "exp_c_exp-c-smoke-009.json"
    assert json.loads(path.read_text(encoding="utf-8"))["format"] == SUMMARY_FORMAT


def test_tiny_run_provenance_and_failures(tiny_run: tuple[Path, Path], tmp_path: Path) -> None:
    _, run_dir = tiny_run
    copy = tmp_path / "run"
    shutil.copytree(run_dir, copy)
    manifest = json.loads((copy / "manifest.json").read_text(encoding="utf-8"))
    manifest.update(
        {"profile": "full", "allow_dirty": False, "git": {"commit": "abc", "dirty": False}}
    )
    (copy / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    # the cell summaries still say smoke with two chains each, so the full
    # profile's grid is complete by name but every cell is incomplete
    provenance = summarize_exp_c(copy)["provenance"]
    assert provenance["clean_tree"] is True and provenance["confirmatory"] is False
    assert provenance["complete_grid"] is True and len(provenance["cells_incomplete"]) == 5
    manifest["profile"] = "smoke"
    (copy / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    provenance = summarize_exp_c(copy)["provenance"]
    assert provenance["cells_incomplete"] == [] and provenance["confirmatory"] is False
    manifest["allow_dirty"] = True
    (copy / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert summarize_exp_c(copy)["provenance"]["clean_tree"] is False
    # a shared quiet window that differs stops the analysis
    name = "C1-p08-n05-match-l500-q02"
    cell = read_cell_summary(summary_path(copy, name))
    cell["chains"][0]["verdicts"][0]["pooled"]["refusal"]["T"] = 0.75
    write_cell_summary(summary_path(copy, name), cell)
    with pytest.raises(RunError, match="disagree on their shared quiet windows"):
        summarize_exp_c(copy)
    summary_path(copy, name).unlink()
    with pytest.raises(RunError, match="lacks cell summaries"):
        summarize_exp_c(copy)
    (copy / "manifest.json").write_text(json.dumps({**manifest, "cells": []}), encoding="utf-8")
    with pytest.raises(RunError, match="none listed"):
        summarize_exp_c(copy)


# --- quantiles and blocks --------------------------------------------------------


def test_detection_quantile_follows_the_inverse_ecdf_rule() -> None:
    assert detection_quantile([], 14, 0.5) == "not estimable"
    assert detection_quantile([1, 1, None, None], 14, 0.5) == 1
    assert detection_quantile([1, 1, None, None], 14, 0.9) == "above 14"
    assert detection_quantile([3, 5, 9, 14], 14, 0.9) == 14
    assert detection_quantile([None], 14, 0.5) == "above 14"
    block = detection_block([2, 2, 9, None], 14)
    assert block["total"] == 4 and block["censored"] == 1
    assert block["within"]["2"]["count"] == 2 and block["within"]["14"]["count"] == 3
    assert block["median"] == 2 and block["p90"] == "above 14"
    assert block["histogram"] == {"2": 2, "9": 1}
    empty = detection_block([], 14)
    assert empty["within"]["1"]["rate"] is None and empty["median"] == "not estimable"


# --- a synthetic full grid with known answers ------------------------------------


def _unit(*parts: Any) -> float:
    digest = hashlib.sha256(":".join(str(part) for part in parts).encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def _records(
    cell: ChainCell, replication: int, *, e_delay: int | None, late: bool = False
) -> list[dict[str, Any]]:
    """Verdict records of one chain whose quiet windows depend on the geometry only.

    Quiet windows: small T per scorer from a hash of (geometry, scorer,
    replication, window); a transient pooled false alarm at window 5 in
    every tenth replication; a sticky e-process alarm at window 9 in every
    twenty-fifth replication. Post-change windows: the primary scorer's T is
    the level; the e-process alarms ``e_delay`` windows after the change
    (never when None); ``late`` delays the pooled rejection to the third
    post-change window. CUSUM and Page-Hinkley flags come from the real
    detectors over the series, so the S-C5 default check passes.
    """

    quiet, post = cell.pre_change_windows, cell.post_change_windows
    geometry = (cell.panel_size, cell.samples)
    primary = PRIMARY[cell.kind]
    sign = -1.0 if primary == "normalized_match" else 1.0
    series: dict[str, list[float]] = {}
    for scorer in SCORERS:
        values = []
        for index in range(1, quiet + post + 1):
            if index <= quiet:
                values.append(round((_unit(geometry, scorer, replication, index) - 0.5) / 10, 6))
            elif scorer == primary:
                values.append(sign * float(cell.level))
            else:
                values.append(0.0)
        series[scorer] = values
    transient = replication % 10 == 3
    sticky = replication % 25 == 7
    # the detectors are sticky, so the alarm at window t is the first crossing
    # over the whole series being at or before t
    cusum_first = {
        scorer: cusum(series[scorer], k=0.1, h=0.4).alarm_index for scorer in SCORERS
    }
    ph_first = {
        scorer: page_hinkley(series[scorer], delta=0.05, threshold=0.5).alarm_index
        for scorer in SCORERS
    }
    records = []
    for index in range(1, quiet + post + 1):
        after = index - quiet
        pooled: dict[str, Any] = {}
        sequential: dict[str, Any] = {}
        rejected_scorers: list[str] = []
        alarms: list[tuple[str, str]] = []
        for scorer in SCORERS:
            rejected = (scorer == "normalized_match" and transient and index == 5) or (
                scorer == primary and after >= (3 if late else 1)
            )
            if rejected:
                rejected_scorers.append(scorer)
            cs_alarm = cusum_first[scorer] is not None and cusum_first[scorer] + 1 <= index
            ph_alarm = ph_first[scorer] is not None and ph_first[scorer] + 1 <= index
            e_alarm = scorer == "normalized_match" and (
                (sticky and index >= 9) or (e_delay is not None and after >= e_delay)
            )
            warning = scorer == "normalized_match" and (
                e_alarm or (e_delay is not None and after == e_delay - 1 and after >= 1)
            )
            if e_alarm:
                alarms.append(("e-process alarm", scorer))
            if cs_alarm:
                alarms.append(("cusum alarm", scorer))
            if ph_alarm:
                alarms.append(("page-hinkley alarm", scorer))
            pooled[scorer] = {
                "T": series[scorer][index - 1],
                "p": 0.001 if rejected else 0.6,
                "p_holm": 0.007 if rejected else 1.0,
                "probes": cell.panel_size,
                "rejected": rejected,
            }
            sequential[scorer] = {
                "cusum_alarm": cs_alarm,
                "ph_alarm": ph_alarm,
                "e_alarm": e_alarm,
                "e": 40.0 if e_alarm else 0.5,
                "e_max": 40.0 if e_alarm else (20.0 if warning else 1.0),
                "e_threshold": 40.0,
            }
        if rejected_scorers:
            state, rule = "drift", f"pooled test rejected for {rejected_scorers[0]}"
        elif alarms:
            state, rule = "drift", f"{alarms[0][0]} for {alarms[0][1]}"
        elif any(sequential[s]["e_max"] >= 20.0 for s in SCORERS):
            state, rule = "warning", "e-process at half threshold for normalized_match"
        else:
            state, rule = "stable", "no rule fired"
        records.append(
            {
                "window_index": index,
                "window_id": f"{cell.part}-r{replication:03d}-w{index:02d}",
                "sequence_index": index,
                "node_id": f"node-{cell.name}-{replication}-{index}",
                "state": state,
                "rule_fired": rule,
                "pooled": pooled,
                "sequential": sequential,
            }
        )
    return records


def synthetic_cell(
    cell: ChainCell, run_id: str, *, e_delay: int | None, late: bool = False
) -> dict[str, Any]:
    chains = []
    for replication in range(cell.replications):
        records = _records(cell, replication, e_delay=e_delay, late=late)
        reduced = first_alarms(records, cell.change_window, SCORERS)
        reduced.update({"kind": cell.kind, "level": cell.level, "replication": replication})
        chains.append(
            {
                "replication": replication,
                "monitor_id": f"{cell.name}-r{replication:03d}",
                "window_ids": [],
                "salts": [],
                "change_window": cell.change_window,
                "verdicts": records,
                "first_alarms": reduced,
            }
        )
    return {
        "format": CELL_SUMMARY_FORMAT,
        "run_id": run_id,
        "experiment": "EXP-C",
        "profile": "full",
        "cell": cell.name,
        "part": cell.part,
        "panel_size": cell.panel_size,
        "samples": cell.samples,
        "kind": cell.kind,
        "level": cell.level,
        "baseline_windows": 1,
        "pre_change_windows": cell.pre_change_windows,
        "post_change_windows": cell.post_change_windows,
        "replications": cell.replications,
        "primary_scorer": PRIMARY[cell.kind],
        "change_window": cell.change_window,
        "current_windows": cell.current_windows,
        "windows_per_replication": cell.windows_per_replication,
        "panel_digest": "panel",
        "config_digest": "config",
        "protocol_digest": "protocol",
        "scorers": list(SCORERS),
        "alpha": 0.05,
        "store": f"stores/{cell.name}.sqlite",
        "store_sha256": "0" * 64,
        "store_bytes": 1,
        "store_sidecars": [],
        "archive": f"stores/{cell.name}.zip",
        "archive_sha256": "1" * 64,
        "archive_bytes": 1,
        "timing": {"seconds_per_chain": 1.0, "verdicts": 1},
        "chains": chains,
    }


E_DELAY = {"0.05": None, "0.1": None, "0.2": 9, "0.3": 6, "0.5": 3}


@pytest.fixture(scope="module")
def synthetic_run(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A full-profile run directory with synthetic cells over the real grid."""

    root = tmp_path_factory.mktemp("synthetic") / "repo"
    run_dir = root / EXPERIMENT_DIR / "runs" / "exp-c-full-001"
    run_dir.mkdir(parents=True)
    shutil.copy(EXP_C_PROTOCOL, run_dir / "protocol.frozen.json")
    protocol = load_protocol(run_dir / "protocol.frozen.json")
    cells = chain_cells(protocol, "full")
    names = []
    for cell in cells:
        # keep the synthetic grid small: 100 chains where H-C1 counts them, 50 elsewhere
        small = ChainCell(**{**cell.__dict__, "replications": cell.replications})
        e_delay = E_DELAY[cell.level]
        if cell.pre_change_windows == 28 and e_delay is not None:
            e_delay += 3  # the quiet-period penalty of H-C2
        late = cell.kind == "refusal" and cell.level == "0.2"  # the falsified H-C1 cell
        document = synthetic_cell(small, "exp-c-full-001", e_delay=e_delay, late=late)
        document["protocol_digest"] = protocol.digest
        write_cell_summary(summary_path(run_dir, cell.name), document)
        names.append(cell.name)
    manifest = {
        "run_id": "exp-c-full-001",
        "experiment": "EXP-C",
        "profile": "full",
        "status": "completed",
        "protocol": {
            "path": PROTOCOL.as_posix(),
            "version": protocol.version,
            "digest": protocol.digest,
        },
        "config_digest": "config",
        "git": {"commit": "deadbeef", "dirty": False},
        "allow_dirty": False,
        "resume": False,
        "only_cells": [],
        "cells": [{"cell": name, "timing": {"seconds_per_chain": 1.0}} for name in names],
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return run_dir


def _exp_a_run(tmp_path: Path, *, profile: str = "full", chains: int = 60) -> Path:
    """A synthetic EXP-A run directory with an A2 cell of 28 null windows."""

    run_dir = tmp_path / "exp-a"
    (run_dir / "cells").mkdir(parents=True)
    detail = []
    for replication in range(chains):
        verdicts = []
        for index in range(1, 29):
            pooled = {
                scorer: {"T": round((_unit("a2", scorer, replication, index) - 0.5) / 10, 6)}
                for scorer in SCORERS
            }
            verdicts.append({"window_index": index, "pooled": pooled})
        detail.append({"replication": replication, "verdicts": verdicts})
    (run_dir / "cells" / "A2-p24-n10.json").write_text(
        json.dumps({"scorers": list(SCORERS), "replications_detail": detail}), encoding="utf-8"
    )
    (run_dir / "manifest.json").write_text(
        json.dumps({"run_id": "exp-a-full-001", "profile": profile, "protocol": {"digest": "a"}}),
        encoding="utf-8",
    )
    return run_dir


def test_synthetic_grid_h_c1_h_c2_s_c3_s_c4_and_export(synthetic_run: Path, tmp_path: Path) -> None:
    summary = summarize_exp_c(synthetic_run, _exp_a_run(tmp_path))
    assert summary["provenance"]["confirmatory"] is True
    assert all(block["agree"] for block in summary["shared_window_check"].values())
    assert summary["shared_window_check"]["p24-n10"]["reference"].endswith("q28")
    # S-C3: the distinct quiet chains at the EXP-D geometry carry the shared false alarms
    q14 = summary["s_c3"]["p24-n10-q14"]
    assert q14["cell"] == "C1-p24-n10-match-l050-q14" and q14["note"] is not None
    assert q14["state"]["sticky_before_change"]["count"] == 4  # replications 7, 32, 57, 82
    assert q14["state"]["drift_before_change"]["count"] == 14  # 10 transient + 4 sticky
    assert q14["detectors"]["eprocess"]["union"]["count"] == 4
    assert q14["detectors"]["pooled"]["per_scorer"]["normalized_match"]["count"] == 10
    assert summary["s_c3"]["p24-n10-q28"]["note"] is None
    assert summary["s_c3"]["p24-n05-q14"]["state"]["sticky_before_change"]["total"] == 50
    # H-C1: 15 cells over the 96 eligible chains, one cell falsified
    h = summary["h_c1"]
    assert h["family_size"] == 15 and h["not_estimable"] == []
    rows = {row["cell"]: row for row in h["cells"]}
    good = rows["C1-p24-n10-match-l200-q14"]
    assert good["eligible"] == 96 and good["within_2"]["count"] == 96
    assert good["unconditional_within_2"]["count"] == 96
    assert good["unconditional_within_2"]["total"] == 100
    assert good["raw_p"] == 1.0 and good["falsified_after_holm"] is False
    first_step = max(k for k in range(97) if binomial_cdf(k, 96, 0.9) <= 0.05 / 15)
    unadjusted = max(k for k in range(97) if binomial_cdf(k, 96, 0.9) <= 0.05)
    assert good["critical_count_first_step"] == first_step == 77
    assert good["critical_count_unadjusted"] == unadjusted == 80
    assert good["power_first_step"]["0.8"] == pytest.approx(binomial_cdf(77, 96, 0.8))
    bad = rows["C1-p24-n10-refusal-l200-q14"]
    assert bad["within_2"]["count"] == 0 and bad["falsified_after_holm"] is True
    assert bad["unadjusted_flag"] is True
    assert h["falsified_after_holm"] == ["C1-p24-n10-refusal-l200-q14"]
    assert good["ineligible_replications"] == [7, 32, 57, 82]
    # H-C2: every eligible pair has the three-window penalty
    h2 = summary["h_c2"]
    assert h2["computed"] is True and h2["criterion_met_both_levels"] is True
    level = h2["levels"][0]
    assert level["eligible_pairs"] == 48 and level["excluded_pre_change_replications"] == [7, 32]
    assert level["pairs_at_least_3"] == 48
    table = h2["by_quiet_length"]["0.3"]["quiet_lengths"]
    assert table["0"]["median"] == 6 and table["28"]["median"] == 9
    assert table["14"]["cell"] == "C1-p24-n10-match-l300-q14" and table["14"]["chains"] == 50
    # the sticky alarm sits at quiet window 9: absent at 7, present at 14 and 28
    assert table["7"]["pre_change_alarms"] == 0 and table["14"]["pre_change_alarms"] == 2
    assert table["28"]["pre_change_alarms"] == 2 and table["28"]["censored"] == 0
    assert h2["by_quiet_length"]["0.3"]["median_slope_per_quiet_window"] == pytest.approx(
        3 / 28, abs=0.05
    )
    # S-C4 compares N 5, 10 and 20 for the match kind
    assert sorted(summary["s_c4"]["0.2"]) == ["10", "20", "5"]
    assert summary["s_c4"]["0.2"]["5"]["cell"] == "C2-p24-n05-match-l200-q14"
    assert summary["s_c4"]["0.1"]["10"]["state"]["within"]["1"]["count"] == 96
    # S-C5: the defaults reproduce the records, the grid is filled, a pair is recommended
    s5 = summary["s_c5"]
    assert s5["default_check"]["mismatch_count"] == 0
    assert s5["null_chains"] == {"cell": "C3-p24-n10-match-l300-q28", "chains": 50}
    assert s5["exp_a"]["run_id"] == "exp-a-full-001"
    assert len(s5["cusum"]["grid"]) == 24 and len(s5["page_hinkley"]["grid"]) == 12
    row = next(r for r in s5["cusum"]["grid"] if r["params"] == [0.1, 0.4])
    assert row["a2_false_alarm"]["total"] == 60 and row["c3_false_alarm"]["total"] == 50
    assert set(row["delay_level_0.2"]) == set(PRIMARY)
    assert row["delay_level_0.2"]["match"]["alarms"] + row["delay_level_0.2"]["match"][
        "misses"
    ] + row["delay_level_0.2"]["match"]["pre_change"] == 100
    assert s5["cusum"]["recommended"] is not None
    assert s5["page_hinkley"]["recommended"] is not None
    # export: the D90 over eligible chains per kind, the failing kind named
    ex = summary["export"]
    assert ex["d90_level_0.2_by_kind"]["match"]["d90"] == 1
    assert ex["d90_level_0.2_by_kind"]["refusal"]["excluded"] is True
    assert ex["kinds_excluded"] == ["refusal"] and ex["bound_days"] == 1
    assert ex["sticky_pre_change_rate_q14"]["count"] == 4
    json.dumps(summary, allow_nan=False)


def test_synthetic_grid_without_exp_a_or_with_a_smoke_exp_a(
    synthetic_run: Path, tmp_path: Path
) -> None:
    manifest = json.loads((synthetic_run / "manifest.json").read_text(encoding="utf-8"))
    summaries = [
        read_cell_summary(summary_path(synthetic_run, entry["cell"]))
        for entry in manifest["cells"]
        if entry["cell"] in ("C1-p24-n10-match-l200-q14", "C3-p24-n10-match-l300-q28")
    ]
    without = s_c5(summaries, None)
    assert without["cusum"]["recommended"] is None and without["exp_a"] is None
    row = without["cusum"]["grid"][0]
    assert row["a2_false_alarm"] is None and row["c3_false_alarm"]["total"] == 50
    smoke = s_c5(summaries, _exp_a_run(tmp_path, profile="smoke"))
    assert smoke["exp_a"]["profile"] == "smoke" and smoke["cusum"]["recommended"] is None
    assert smoke["cusum"]["recommendation_withheld"] == "no EXP-A full run supplied"
    (tmp_path / "exp-a" / "cells" / "A2-p24-n10.json").unlink()
    with pytest.raises(RunError, match="no A2-p24-n10"):
        s_c5(summaries, tmp_path / "exp-a")
    with pytest.raises(RunError, match="not a run directory"):
        s_c5(summaries, tmp_path / "nowhere")


def test_default_check_reports_a_chain_whose_record_disagrees(synthetic_run: Path) -> None:
    name = "C1-p24-n10-match-l200-q14"
    cell = read_cell_summary(summary_path(synthetic_run, name))
    chain = cell["chains"][0]
    chain["verdicts"][20]["sequential"]["output_chars"]["cusum_alarm"] = True
    result = default_check([cell])
    assert result["chains_passed"] == 99 and result["mismatch_count"] == 1
    assert result["mismatches"][0]["detector"] == "cusum"
    assert (name, 0) not in result["passed"]
    chain["verdicts"][3]["pooled"]["refusal"]["T"] = None
    result = default_check([cell])
    assert result["mismatches"][0]["reason"] == "missing T"
    assert result["mismatch_count"] == 2


def test_h_c1_and_export_edge_cases() -> None:
    def block(
        cell: str, kind: str, level: str, eligible: int, within: int, p90: Any
    ) -> dict[str, Any]:
        return {
            "cell": cell,
            "part": "C1",
            "panel_size": 24,
            "samples": 10,
            "pre_change_windows": 14,
            "kind": kind,
            "level": level,
            "state": {
                "ineligible_replications": [],
                "unconditional_within": {"2": {"count": within, "total": 100}},
                "drift": {
                    "total": eligible,
                    "within": {"2": {"count": within, "total": eligible}},
                    "p90": p90,
                },
            },
        }

    cells = [
        block("C1-a", "match", "0.2", 0, 0, "not estimable"),
        block("C1-b", "length", "0.2", 100, 95, "above 14"),
        block("C1-c", "refusal", "0.3", 100, 60, 5),
    ]
    result = h_c1(cells)
    assert result["family_size"] == 3 and result["not_estimable"] == ["C1-a"]
    rows = {row["cell"]: row for row in result["cells"]}
    assert rows["C1-a"]["raw_p"] == 1.0 and rows["C1-a"]["power_first_step"] is None
    assert rows["C1-a"]["falsified_after_holm"] is False
    assert rows["C1-c"]["falsified_after_holm"] is True
    assert rows["C1-b"]["falsified_after_holm"] is False
    exported = export(cells, result, {})
    assert exported["kinds_excluded"] == ["match"] and exported["bound_days"] == "above 14"
    assert exported["sticky_pre_change_rate_q14"] is None
    assert export([], result, {})["bound_days"] is None
    passing = [
        block("C1-d", "match", "0.2", 100, 100, 3),
        block("C1-e", "length", "0.2", 100, 100, 7),
    ]
    assert export(passing, h_c1(passing), {})["bound_days"] == 7


def test_summarize_cell_counts_states_and_rules(synthetic_run: Path) -> None:
    cell = read_cell_summary(summary_path(synthetic_run, "C1-p24-n10-refusal-l200-q14"))
    block = summarize_cell(cell)
    state = block["state"]
    assert state["ineligible"]["count"] == 4 and state["pre_change_drift"]["count"] == 14
    assert state["pre_change_first_rule"] == {
        "e-process alarm for normalized_match": 4,
        "pooled test rejected for normalized_match": 10,
    }
    assert state["first_drift_rule"] == {"pooled test rejected for refusal": 96}
    assert state["drift"]["median"] == 3 and state["drift"]["within"]["2"]["count"] == 0
    assert block["e_before_change"]["normalized_match"]["n"] == 100
    pooled = block["detectors"]["refusal"]["pooled"]
    assert pooled["pre_change"]["count"] == 0 and pooled["all_chains"]["total"] == 100
    warning = block["detectors"]["normalized_match"]["eprocess_warning"]
    assert warning["pre_change"]["count"] == 4
    assert shared_window_check([cell])["p24-n10"]["chains_compared"] == 0


def test_h_c2_table_marks_absent_quiet_lengths(synthetic_run: Path) -> None:
    manifest = json.loads((synthetic_run / "manifest.json").read_text(encoding="utf-8"))
    summaries = [
        read_cell_summary(summary_path(synthetic_run, entry["cell"]))
        for entry in manifest["cells"]
        if not entry["cell"].endswith("q07")
    ]
    result = h_c2(summaries)
    assert result["computed"] is True
    table = result["by_quiet_length"]["0.5"]["quiet_lengths"]
    assert table["7"] is None and table["0"]["median"] == 3 and table["28"]["median"] == 6
    assert result["by_quiet_length"]["0.5"]["median_slope_per_quiet_window"] is None
    # different planned replication counts between the paired cells stop the pairing
    altered = [dict(summary) for summary in summaries]
    for summary in altered:
        if summary["cell"] == "C3-p24-n10-match-l300-q00":
            summary["replications"] = 49
    assert h_c2(altered)["computed"] is False
    assert "different replication counts" in h_c2(altered)["reason"]


def test_s_c5_skips_excluded_chains_and_counts_pre_change_alarms(synthetic_run: Path) -> None:
    manifest = json.loads((synthetic_run / "manifest.json").read_text(encoding="utf-8"))
    summaries = [
        read_cell_summary(summary_path(synthetic_run, entry["cell"]))
        for entry in manifest["cells"]
        if entry["cell"] in ("C1-p24-n10-match-l200-q14", "C3-p24-n10-match-l300-q28")
    ]
    cell = next(s for s in summaries if s["cell"].startswith("C1"))
    # chain 0: a recorded alarm the rerun does not reproduce, so it leaves the grid;
    # chain 1: a quiet window far from zero, so every pair alarms before the change
    cell["chains"][0]["verdicts"][20]["sequential"]["refusal"]["ph_alarm"] = True
    verdicts = cell["chains"][1]["verdicts"]
    for record in verdicts[:14]:
        record["pooled"]["output_chars"]["T"] = 0.9
    series = [record["pooled"]["output_chars"]["T"] for record in verdicts]
    for index, record in enumerate(verdicts, start=1):
        block = record["sequential"]["output_chars"]
        block["cusum_alarm"] = cusum(series[:index], k=0.1, h=0.4).alarm
        block["ph_alarm"] = page_hinkley(series[:index], delta=0.05, threshold=0.5).alarm
    result = s_c5(summaries, None)
    assert result["default_check"]["mismatch_count"] == 1
    row = next(r for r in result["cusum"]["grid"] if r["params"] == [0.1, 0.4])
    match = row["delay_level_0.2"]["match"]
    assert match["pre_change"] == 1 and match["alarms"] == 98
    assert match["alarms"] + match["misses"] + match["pre_change"] == 99
