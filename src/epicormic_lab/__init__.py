"""Experiment code for the epicormic paper.

Scripts under scripts/ and notebooks under notebooks/ are thin front-ends
over this package: they load a frozen protocol, run it through the same
functions, and write the same run manifests. The experiment logic lives here
and nowhere else, so a script run and a notebook run of one protocol are the
same computation.
"""

from __future__ import annotations

from epicormic_lab.pins import EPICORMIC, PINS, POLLARD, Pin, check_installed

__all__ = ["EPICORMIC", "PINS", "POLLARD", "Pin", "__version__", "check_installed"]

__version__ = "0.0.1"
