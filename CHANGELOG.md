# Changelog

All notable changes to this repository are recorded here in the Keep a
Changelog format. Experiment runs are recorded in `LOGBOOK.md` and
`experiments/run_registry.yaml`, not here.

## Unreleased

### Added

- Repository scaffold: rules, layout, and run lifecycle in `README.md`;
  `LOGBOOK.md` and `findings.md` headers; the run registry schema.
- `epicormic_lab.pins`: verified release identities of epicormic 0.1.0 and
  pollard 1.6.0 (tag commits, wheel and sdist digests) with an
  installed-version check.
- `tools/scan_vocabulary.py`, carried over from epicormic and extended to
  notebooks and TeX.
- CI on Ubuntu and Windows with Python 3.10 and 3.12: ruff, mypy, the
  vocabulary scan, and tests with a 100 percent coverage gate.
- `HANDOFF.md`: the runner handoff for Katie and Mike: who runs which
  experiment arm, what exists in the repository today, the locked mock
  instrumentation check, the pinned local control from pollard EXP-001, the
  hosted budget rules, and how results come back.
- EXP-A pre-registration (mock arm): `experiments/exp_a_calibration/`
  with `PREREGISTRATION.md`, `protocol.json` (version 2026-10-28), the
  logbook plan entry, and the first panels under `data/panels/`
  (`canary-24-v1`, `mock-08-v1`, `mock-64-v1`) with digests and checksums.

### Fixed

- The vocabulary scan reports malformed Python on Python 3.10 and 3.11,
  where the tokenizer emits error tokens instead of raising; before this
  such a file passed the scan silently on those versions.
