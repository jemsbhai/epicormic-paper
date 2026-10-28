"""The pinned releases are what is installed, and the pins are well-formed."""

from __future__ import annotations

import importlib.metadata
import re

import pytest

import epicormic_lab
from epicormic_lab import EPICORMIC, PINS, POLLARD, Pin, check_installed

HEX_40 = re.compile(r"^[0-9a-f]{40}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")


def test_package_version_is_a_string() -> None:
    assert isinstance(epicormic_lab.__version__, str)
    assert epicormic_lab.__version__


def test_pins_name_the_two_studied_distributions() -> None:
    assert PINS == (EPICORMIC, POLLARD)
    assert EPICORMIC.name == "epicormic"
    assert EPICORMIC.version == "0.2.0"
    assert POLLARD.name == "pollard"
    assert POLLARD.version == "1.6.0"


@pytest.mark.parametrize("pin", PINS, ids=lambda pin: pin.name)
def test_pin_identity_fields_are_well_formed(pin: Pin) -> None:
    assert HEX_40.match(pin.commit)
    assert HEX_64.match(pin.wheel_sha256)
    assert HEX_64.match(pin.sdist_sha256)
    assert pin.tag == f"v{pin.version}"
    assert pin.wheel == f"{pin.name}-{pin.version}-py3-none-any.whl"
    assert pin.sdist == f"{pin.name}-{pin.version}.tar.gz"
    assert pin.repository == f"https://github.com/jemsbhai/{pin.name}"


@pytest.mark.parametrize("pin", PINS, ids=lambda pin: pin.name)
def test_installed_version_matches_pin(pin: Pin) -> None:
    assert pin.installed_version() == importlib.metadata.version(pin.name)
    assert pin.matches_installed(), (
        f"{pin.name} {pin.installed_version()} is installed; the experiments pin {pin.version}"
    )


def test_check_installed_is_clean_in_a_pinned_environment() -> None:
    assert check_installed() == []


def test_check_installed_reports_a_version_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_version(name: str) -> str:
        return "9.9.9"

    monkeypatch.setattr(importlib.metadata, "version", fake_version)
    assert check_installed((EPICORMIC,)) == ["epicormic 0.2.0 is pinned but 9.9.9 is installed"]


def test_check_installed_reports_a_missing_distribution(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(name: str) -> str:
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, "version", missing)
    assert check_installed((POLLARD,)) == ["pollard 1.6.0 is pinned but not installed"]


def test_pin_is_immutable() -> None:
    with pytest.raises(AttributeError):
        EPICORMIC.version = "0.2.0"  # type: ignore[misc]
