"""Canonical serialization, protocol digests, validation, and the freeze command."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from epicormic_lab.pins import EPICORMIC, POLLARD
from epicormic_lab.protocol import (
    Protocol,
    ProtocolError,
    ProtocolMismatch,
    canonical_bytes,
    load_protocol,
    main,
    protocol_digest,
    validate_protocol,
    verify_protocol,
)

HEX_64 = re.compile(r"^[0-9a-f]{64}$")


def valid_protocol(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "experiment": "EXP-A",
        "version": "2026-09-30",
        "epicormic": EPICORMIC.version,
        "pollard": POLLARD.version,
        "alpha": 0.05,
        "grid": {"N": [5, 10, 20], "replications": 200},
    }
    data.update(overrides)
    return data


def write_json(path: Path, data: Any, **kwargs: Any) -> Path:
    path.write_text(json.dumps(data, **kwargs), encoding="utf-8")
    return path


def test_canonical_bytes_sorts_keys_and_drops_whitespace() -> None:
    assert canonical_bytes({"b": 1, "a": [1, 2, {"z": None, "y": True}]}) == (
        b'{"a":[1,2,{"y":true,"z":null}],"b":1}'
    )


def test_canonical_bytes_keeps_non_ascii_as_utf8() -> None:
    assert canonical_bytes({"k": "\u00e9"}) == '{"k":"\u00e9"}'.encode()


def test_canonical_bytes_keeps_float_repr() -> None:
    assert canonical_bytes({"alpha": 0.05, "big": 1e16}) == b'{"alpha":0.05,"big":1e+16}'


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), {"s": {1, 2}}, {1: "a", "b": 2}, {"lone": "\ud800"}],
    ids=["nan", "inf", "set", "mixed-keys", "lone-surrogate"],
)
def test_canonical_bytes_rejects_what_has_no_canonical_form(value: Any) -> None:
    with pytest.raises(ProtocolError, match="not canonically serializable"):
        canonical_bytes(value)


def test_protocol_digest_is_sha256_of_canonical_bytes() -> None:
    data = valid_protocol()
    assert protocol_digest(data) == hashlib.sha256(canonical_bytes(data)).hexdigest()
    assert HEX_64.match(protocol_digest(data))


json_leaves = st.none() | st.booleans() | st.integers() | st.text()
json_values = st.recursive(
    json_leaves,
    lambda children: (
        st.lists(children, max_size=4) | st.dictionaries(st.text(), children, max_size=4)
    ),
    max_leaves=12,
)


@settings(max_examples=60, deadline=None)
@given(st.dictionaries(st.text(), json_values, max_size=6))
def test_digest_ignores_key_order_and_formatting(data: dict[str, Any]) -> None:
    reversed_keys = dict(reversed(list(data.items())))
    reformatted = json.loads(json.dumps(data, indent=4))
    assert protocol_digest(reversed_keys) == protocol_digest(data)
    assert protocol_digest(reformatted) == protocol_digest(data)


def test_validate_protocol_accepts_a_valid_mapping() -> None:
    data = valid_protocol(version="2026-09-30b")
    assert validate_protocol(data) is data


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (["EXP-A"], "must be a JSON object"),
        ({"experiment": "EXP-A"}, "missing required keys: version, epicormic, pollard"),
        (valid_protocol(experiment="EXP-F"), "experiment must be EXP-A to EXP-E, got 'EXP-F'"),
        (valid_protocol(experiment=1), "experiment must be EXP-A to EXP-E, got 1"),
        (valid_protocol(version="v1"), "version must be a date such as 2026-09-30"),
        (valid_protocol(version=20260930), "version must be a date such as 2026-09-30"),
        (valid_protocol(epicormic="0.2.0"), "epicormic must be pinned to 0.1.0, got '0.2.0'"),
        (valid_protocol(pollard="1.7.0"), "pollard must be pinned to 1.6.0, got '1.7.0'"),
    ],
    ids=[
        "not-object",
        "missing-keys",
        "bad-experiment",
        "non-string-experiment",
        "bad-version",
        "non-string-version",
        "wrong-epicormic",
        "wrong-pollard",
    ],
)
def test_validate_protocol_rejects_malformed_input(data: Any, message: str) -> None:
    with pytest.raises(ProtocolError, match=re.escape(message)):
        validate_protocol(data)


def test_validate_protocol_prefixes_the_path_when_given(tmp_path: Path) -> None:
    path = tmp_path / "protocol.json"
    with pytest.raises(ProtocolError, match=re.escape(f"{path}: protocol must be a JSON object")):
        validate_protocol("text", path)


def test_load_protocol_reads_validates_and_digests(tmp_path: Path) -> None:
    data = valid_protocol()
    path = write_json(tmp_path / "protocol.json", data, indent=2)
    protocol = load_protocol(path)
    assert isinstance(protocol, Protocol)
    assert protocol.path == path
    assert protocol.data == data
    assert protocol.digest == protocol_digest(data)
    assert protocol.experiment == "EXP-A"
    assert protocol.version == "2026-09-30"


def test_load_protocol_digest_does_not_depend_on_file_formatting(tmp_path: Path) -> None:
    data = valid_protocol()
    compact = write_json(tmp_path / "compact.json", data, separators=(",", ":"))
    indented = write_json(tmp_path / "indented.json", data, indent=4, sort_keys=False)
    assert load_protocol(compact).digest == load_protocol(indented).digest


def test_load_protocol_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "protocol.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ProtocolError, match=re.escape(f"{path}: invalid JSON")):
        load_protocol(path)


def test_verify_protocol_returns_the_protocol_on_a_match(tmp_path: Path) -> None:
    data = valid_protocol()
    path = write_json(tmp_path / "protocol.json", data)
    assert verify_protocol(path, protocol_digest(data)).data == data


def test_verify_protocol_raises_on_a_mismatch(tmp_path: Path) -> None:
    data = valid_protocol()
    path = write_json(tmp_path / "protocol.json", data)
    expected = "0" * 64
    with pytest.raises(ProtocolMismatch) as excinfo:
        verify_protocol(path, expected)
    assert excinfo.value.path == path
    assert excinfo.value.expected == expected
    assert excinfo.value.actual == protocol_digest(data)
    actual = protocol_digest(data)
    assert str(excinfo.value) == f"{path}: expected digest {expected}, found {actual}"


def test_main_prints_one_digest_line_per_protocol(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = write_json(tmp_path / "a.json", valid_protocol())
    second = write_json(tmp_path / "c.json", valid_protocol(experiment="EXP-C"))
    assert main([str(first), str(second)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out == [
        f"{protocol_digest(valid_protocol())}  {first}",
        f"{protocol_digest(valid_protocol(experiment='EXP-C'))}  {second}",
    ]


def test_main_expect_succeeds_on_a_match(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_json(tmp_path / "a.json", valid_protocol())
    digest = protocol_digest(valid_protocol())
    assert main([str(path), "--expect", digest]) == 0
    assert capsys.readouterr().out == f"{digest}  {path}\n"


def test_main_expect_exits_1_on_a_mismatch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_json(tmp_path / "a.json", valid_protocol())
    assert main([str(path), "--expect", "f" * 64]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith(f"freeze_protocol: {path}: expected digest")


def test_main_exits_2_on_a_malformed_protocol(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_json(tmp_path / "a.json", valid_protocol(pollard="0.0.0"))
    assert main([str(path)]) == 2
    assert "pollard must be pinned to 1.6.0" in capsys.readouterr().err


def test_main_exits_2_on_a_missing_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "absent.json"
    assert main([str(path)]) == 2
    assert capsys.readouterr().err.startswith("freeze_protocol: ")


def test_main_expect_requires_exactly_one_protocol(tmp_path: Path) -> None:
    first = write_json(tmp_path / "a.json", valid_protocol())
    second = write_json(tmp_path / "b.json", valid_protocol(experiment="EXP-B"))
    with pytest.raises(SystemExit) as excinfo:
        main([str(first), str(second), "--expect", "0" * 64])
    assert excinfo.value.code == 2
