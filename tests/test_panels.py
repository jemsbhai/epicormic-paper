"""The committed canary panels: digests, the v2 variant, and the checksum file."""

from __future__ import annotations

import hashlib

from epicormic.panel import load_panel

from .conftest import REPO

PANELS = REPO / "data" / "panels"
CANARY_V1_DIGEST = "8f7883e3ce8f937212a9cd396b1ce318a88e13fa1b8a7369b673a05f10cb3a75"
CANARY_V2_DIGEST = "aaba1761326e89fe3f6b27521a55d4b56fb2fee87d05400cdeab88ea0bc18fac"


def test_canary_v2_differs_from_v1_only_in_the_sampling_block() -> None:
    v1 = load_panel(PANELS / "canary-24-v1.json")
    v2 = load_panel(PANELS / "canary-24-v2.json")
    assert v1.digest == CANARY_V1_DIGEST and v2.digest == CANARY_V2_DIGEST
    assert v1.name == "canary-24-v1" and v2.name == "canary-24-v2"
    assert v2.probes == v1.probes and len(v2.probes) == 24
    assert (v2.seed_from_attempt, v2.seed_base, v2.seed_field, v2.min_samples) == (
        v1.seed_from_attempt,
        v1.seed_base,
        v1.seed_field,
        v1.min_samples,
    )
    assert v1.sampling == {"max_output_tokens": "200", "temperature": "0.7"}
    assert v2.sampling == {"max_output_tokens": "200"}
    # the dispatched request loses exactly the temperature key
    probe = v1.probes[0]
    expected = {k: v for k, v in v1.request_for(probe, 3).items() if k != "temperature"}
    assert v2.request_for(probe, 3) == expected
    assert "temperature" not in v2.request_for(probe, 3)


def test_checksum_file_matches_every_panel_file() -> None:
    lines = (REPO / "data" / "checksums.sha256").read_text(encoding="utf-8").splitlines()
    listed: dict[str, str] = {}
    for line in lines:
        if line.strip():
            digest, relative = line.split("  ", 1)
            listed[relative] = digest
    files = sorted(path.name for path in PANELS.glob("*.json"))
    assert sorted(name.removeprefix("panels/") for name in listed) == files
    for relative, digest in listed.items():
        assert hashlib.sha256((REPO / "data" / relative).read_bytes()).hexdigest() == digest
