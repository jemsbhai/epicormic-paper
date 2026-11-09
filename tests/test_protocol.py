"""Protocol loading, digests, cells, and panel verification."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from epicormic_lab.pins import EPICORMIC, POLLARD
from epicormic_lab.protocol import (
    PROTOCOL_FORMAT,
    Cell,
    ProtocolError,
    canonical_json,
    load_protocol,
    protocol_digest,
)
from epicormic_lab.providers import DRIFT_KINDS

from .conftest import EXP_C_PROTOCOL, FIRST_PROTOCOL, REAL_PROTOCOL, REPO

FROZEN_DIGEST = "5934acb50e9d4f9403bb64cd038cf492bcd167d7464eef8a1fdd24da2e555de4"
FIRST_DIGEST = "dd7e4356a60b18a9b122a5def9617b761be313f9d7dfa97481e7601a0115210d"
EXP_C_DIGEST = "aeb4cc1e53ea0cd543ea049d70dbb890fbe537aa148410f94e99511dee8027c0"
EXP_C_R3_DIGEST = "ed87bebb3c1bc9aa200c5196a231ed03c7dd34e9fe79739efac3b73d90725ea5"
EXP_C_R2_DIGEST = "d176f31ebc77cc9f28e5dcbefcca77e88f31fbea16c300cb9ebd2c1aac2eda4f"
EXP_C_FIRST_DIGEST = "ef5062ae6a7da040e1b4194e79482de6d3d36e61923b12dcda0af7acd5f1124e"


def test_frozen_protocol_digest_is_unchanged() -> None:
    protocol = load_protocol(REAL_PROTOCOL)
    assert protocol.digest == FROZEN_DIGEST
    assert protocol.experiment == "EXP-A"
    assert protocol.version == "2026-10-28-r2"
    assert protocol.arm == "mock"
    protocol.require_digest(FROZEN_DIGEST)
    first = load_protocol(FIRST_PROTOCOL)
    assert first.digest == FIRST_DIGEST and first.version == "2026-10-28"
    assert protocol.document["supersedes"]["digest"] == FIRST_DIGEST


def test_exp_c_protocol_revision_is_consistent() -> None:
    protocol = load_protocol(EXP_C_PROTOCOL)
    assert protocol.digest == EXP_C_DIGEST
    assert protocol.experiment == "EXP-C" and protocol.version == "2026-11-09-r4"
    software = protocol.document["software"]
    assert software == {"epicormic": EPICORMIC.version, "pollard": POLLARD.version}
    # the superseded versions stay in place verbatim, each with its digest
    r3 = load_protocol(EXP_C_PROTOCOL.with_name("protocol.2026-11-05-r3.json"))
    assert r3.digest == EXP_C_R3_DIGEST and r3.version == "2026-11-05-r3"
    r2 = load_protocol(EXP_C_PROTOCOL.with_name("protocol.2026-10-30-r2.json"))
    assert r2.digest == EXP_C_R2_DIGEST and r2.version == "2026-10-30-r2"
    assert protocol.document["supersedes"]["digest"] == EXP_C_R3_DIGEST
    assert r3.document["supersedes"]["digest"] == EXP_C_R2_DIGEST
    assert r2.document["supersedes"]["digest"] == EXP_C_FIRST_DIGEST
    earlier = [entry["digest"] for entry in protocol.document["supersedes"]["earlier"]]
    assert earlier == [EXP_C_R2_DIGEST, EXP_C_FIRST_DIGEST]
    # r4 applies the sizing rule: only the full replication counts (and the C3
    # note that quotes them) differ from r3 in the design keys
    for key in ("provider", "analysis", "panels", "software", "drifts"):
        assert r3.document[key] == protocol.document[key] == r2.document[key]
    for part, spec in protocol.document["parts"].items():
        before = r3.document["parts"][part]
        assert spec["replications"]["smoke"] == before["replications"]["smoke"] == 2
        assert before["replications"]["full"] == {"C1": 100, "C2": 50, "C3": 50}[part]
        assert spec["replications"]["full"] == {"C1": 60, "C2": 30, "C3": 30}[part]
        unchanged = {k: v for k, v in spec.items() if k not in ("replications", "note")}
        assert unchanged == {k: v for k, v in before.items() if k not in ("replications", "note")}
    assert "first 30 replications" in protocol.document["parts"]["C3"]["note"]
    assert "applied in version 2026-11-09-r4" in protocol.document["run"]["sizing"]
    definitions = protocol.document["outcomes"]["definitions"]
    assert "eligible" in definitions["state_delay"]
    assert "sticky" in definitions["state_eligibility"]
    assert protocol.document["artifacts"]["per_cell_summary"].startswith(
        "runs/<run_id>/cells/<cell>.json.gz"
    )
    assert protocol.verify_panels(REPO) == {
        "data/panels/canary-24-v1.json": protocol.document["panels"]["24"]["digest"]
    }
    # the same analysis document as EXP-A r2, hence the same config digest
    exp_a = load_protocol(REAL_PROTOCOL)
    assert protocol.analysis_config().digest == exp_a.analysis_config().digest
    kinds = protocol.document["drifts"]["kinds"]
    assert {kind: spec["primary_scorer"] for kind, spec in kinds.items()} == DRIFT_KINDS
    parts = protocol.document["parts"]
    chains = sum(
        len(part["kinds"])
        * len(part["levels"])
        * len(part["samples_per_probe"])
        * len(part["pre_change_windows"])
        * part["replications"]["full"]
        for part in parts.values()
    )
    assert chains == 1800
    verdicts = sum(
        len(part["kinds"])
        * len(part["levels"])
        * len(part["samples_per_probe"])
        * part["replications"]["full"]
        * (quiet + part["post_change_windows"])
        for part in parts.values()
        for quiet in part["pre_change_windows"]
    )
    assert verdicts == 49_980


def test_protocol_software_matches_the_pins() -> None:
    software = load_protocol(REAL_PROTOCOL).document["software"]
    assert software == {"epicormic": EPICORMIC.version, "pollard": POLLARD.version}
    # the superseded version names the release it was written against
    assert load_protocol(FIRST_PROTOCOL).document["software"]["epicormic"] == "0.1.0"


def test_canonical_json_is_sorted_and_compact() -> None:
    assert canonical_json({"b": 1, "a": [1.5, "x"]}) == b'{"a":[1.5,"x"],"b":1}'
    assert protocol_digest({"a": 1}) == protocol_digest({"a": 1})


def test_real_grid_has_fourteen_cells_and_the_registered_workload() -> None:
    protocol = load_protocol(REAL_PROTOCOL)
    cells = protocol.cells("full")
    assert len(cells) == 14
    nodes = sum(
        c.replications * c.windows_per_replication * c.panel_size * c.samples for c in cells
    )
    verdicts = sum(c.replications * c.current_windows for c in cells)
    assert nodes == 4_274_880
    assert verdicts == 8_020
    assert cells[0] == Cell("A1", 8, 5, 1, 1, 200)
    assert cells[0].name == "A1-p08-n05"
    assert protocol.cells("smoke")[0].replications == 3


def test_real_panels_match_their_digests() -> None:
    protocol = load_protocol(REAL_PROTOCOL)
    digests = protocol.verify_panels(REPO)
    assert digests["data/panels/canary-24-v1.json"].startswith("8f7883e3")
    assert len(digests) == 3


def test_analysis_config_flattens_the_sequential_block() -> None:
    protocol = load_protocol(REAL_PROTOCOL)
    document = protocol.analysis_document()
    assert "sequential" not in document
    assert document["cusum"] == {"k": "0.1", "h": "0.4"}
    config = protocol.analysis_config()
    assert "latency_s" not in config.scorers
    assert config.permutations == 2000
    assert len(config.digest) == 64


def test_profile_and_panel_errors(repo: Path) -> None:
    protocol = load_protocol(repo / "experiments" / "exp_a_calibration" / "protocol.json")
    with pytest.raises(ProtocolError, match="profile"):
        protocol.cells("nightly")
    with pytest.raises(ProtocolError, match="no panel of size 7"):
        protocol.panel_entry(7)
    with pytest.raises(ProtocolError, match="registered under"):
        protocol.require_digest("0" * 64)


def test_panel_digest_and_size_mismatches(repo: Path) -> None:
    path = repo / "experiments" / "exp_a_calibration" / "protocol.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["panels"]["8"]["digest"] = "0" * 64
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ProtocolError, match="panel digest"):
        load_protocol(path).load_panel(repo, 8)
    document = json.loads(REAL_PROTOCOL.read_text(encoding="utf-8"))
    document["panels"]["9"] = document["panels"]["8"]
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ProtocolError, match="8 probes, protocol expects 9"):
        load_protocol(path).load_panel(repo, 9)


def test_duplicate_sequential_key_is_rejected(repo: Path) -> None:
    path = repo / "experiments" / "exp_a_calibration" / "protocol.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["analysis"]["cusum"] = {"k": "0.2", "h": "0.4"}
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ProtocolError, match="twice"):
        load_protocol(path).analysis_document()


def test_load_protocol_rejects_bad_files(tmp_path: Path) -> None:
    bad = tmp_path / "p.json"
    bad.write_text("{", encoding="utf-8")
    with pytest.raises(ProtocolError, match="not valid JSON"):
        load_protocol(bad)
    bad.write_text(json.dumps({"format": "other"}), encoding="utf-8")
    with pytest.raises(ProtocolError, match=PROTOCOL_FORMAT):
        load_protocol(bad)
    bad.write_text(json.dumps({"format": PROTOCOL_FORMAT, "experiment": "x"}), encoding="utf-8")
    with pytest.raises(ProtocolError, match="lacks the 'version' key"):
        load_protocol(bad)


def test_require_software_matches_the_pins(repo: Path) -> None:
    path = repo / "experiments" / "exp_a_calibration" / "protocol.json"
    load_protocol(path).require_software()
    document = json.loads(path.read_text(encoding="utf-8"))
    document["software"]["epicormic"] = "0.1.0"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ProtocolError, match="repository pins"):
        load_protocol(path).require_software()
    with pytest.raises(ProtocolError, match="repository pins"):
        load_protocol(FIRST_PROTOCOL).require_software()
