"""Pinned identities of the software under study.

The experiments study epicormic 0.2.0 on pollard 1.6.0 exactly as released.
Every value below was verified by downloading the artifact from PyPI and
hashing it with SHA-256, and by resolving the release tag on GitHub with
`git ls-remote`: pollard on 2026-09-27, epicormic 0.2.0 on 2026-10-28 (it
replaced 0.1.0 before any registered run, see the EXP-A plan addendum in
LOGBOOK.md). The test suite checks the installed versions
against these pins, and every run manifest records them, so a run can never
start against a different release by accident.
"""

from __future__ import annotations

import importlib.metadata
from dataclasses import dataclass


@dataclass(frozen=True)
class Pin:
    """One pinned distribution: its release identity on PyPI and on GitHub."""

    name: str
    version: str
    repository: str
    tag: str
    commit: str
    wheel: str
    wheel_sha256: str
    sdist: str
    sdist_sha256: str

    def installed_version(self) -> str:
        """Return the version of the distribution installed in this interpreter."""
        return importlib.metadata.version(self.name)

    def matches_installed(self) -> bool:
        """Return True when the installed version equals the pinned one."""
        return self.installed_version() == self.version


EPICORMIC = Pin(
    name="epicormic",
    version="0.2.0",
    repository="https://github.com/jemsbhai/epicormic",
    tag="v0.2.0",
    commit="40bd810881bc6b4a646b1c79f777b2a42a9fe190",
    wheel="epicormic-0.2.0-py3-none-any.whl",
    wheel_sha256="15c0051d97275dc5434e2abf353cb8b9e25f249f284ba1c36355e39b00abd3a0",
    sdist="epicormic-0.2.0.tar.gz",
    sdist_sha256="1530fad6dfdad0545c15f3ad14cf0b27c7d0075bf9614b57bc2b189f67334ad5",
)

POLLARD = Pin(
    name="pollard",
    version="1.6.0",
    repository="https://github.com/jemsbhai/pollard",
    tag="v1.6.0",
    commit="e9d02af06a2d41403222f81ba623397b8904fdd7",
    wheel="pollard-1.6.0-py3-none-any.whl",
    wheel_sha256="569fb5f130a82c9be327b8dcbd285e3be063200bd9773ca15c5d6bb62edd627f",
    sdist="pollard-1.6.0.tar.gz",
    sdist_sha256="e9a43a52e6875add922d9749028f2c96e7e83dd138ff65ef4d3f834485617fec",
)

PINS: tuple[Pin, ...] = (EPICORMIC, POLLARD)


def check_installed(pins: tuple[Pin, ...] = PINS) -> list[str]:
    """Return one message per pin whose installed version differs.

    An empty list means every pinned distribution is installed at its pinned
    version. A missing distribution is reported the same way as a wrong one.
    """
    problems: list[str] = []
    for pin in pins:
        try:
            installed = pin.installed_version()
        except importlib.metadata.PackageNotFoundError:
            problems.append(f"{pin.name} {pin.version} is pinned but not installed")
            continue
        if installed != pin.version:
            problems.append(f"{pin.name} {pin.version} is pinned but {installed} is installed")
    return problems
