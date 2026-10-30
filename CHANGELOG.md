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
- EXP-A runner and analysis: `epicormic_lab.protocol` (frozen protocols,
  canonical digests, cells, panel checks), `providers` (the mock null
  provider and the per-window seed salt), `stats` (exact binomial tools in
  pure Python), `environment` (snapshots), `registry` (append-only YAML
  writer), `exp_a` (cells, run directories, manifests, the recompute check),
  `analysis` (the committed summary), with `scripts/freeze_protocol.py`,
  `snapshot_environment.py`, `run_exp_a.py`, `analyze_exp_a.py`, and tests at
  100 percent line coverage.
- EXP-C pre-registration (mock arm): `experiments/exp_c_sequential/` with
  `PREREGISTRATION.md`, `protocol.json` (version 2026-10-29), the logbook
  plan entry, and the sizing pilot `pilot/pilot-seed7.json`. In support:
  `epicormic_lab.providers` gains the five drift kinds
  (`drifted_provider`) and the request-hash `mixture` that grades the tool
  swap and the length padding; `epicormic_lab.chains` observes and analyses
  change-point chains and reduces them to first alarms, delays and realised
  effects; `scripts/pilot_exp_c.py` runs the pilot.

### Changed

- Pins move to epicormic 0.2.0 (tag `v0.2.0` at
  `40bd810881bc6b4a646b1c79f777b2a42a9fe190`, PyPI wheel and sdist digests
  in `pins.py`), which corrects the e-process null (D27) and replaced 0.1.0
  before any registered run. EXP-A protocol version 2026-10-28-r2
  (`protocol.2026-10-28-r2.json`) pins it and restates H-A2 against the
  threshold in force; version 2026-10-28 stays in place unrun, with a dated
  logbook addendum. `HANDOFF.md` carries the regenerated locked output and
  the new digest; `scripts/run_exp_a.py` defaults to the current protocol.

### Fixed

- EXP-C protocol 2026-10-30-r2 preserves shared baseline seeds and tests
  H-C2 by an exact paired three-window threshold test, with Holm across
  levels. It defines the restricted-delay endpoint, whole-pair exclusions
  for pre-change alarms, censoring, ties and incomplete-data checks. The
  original protocol is retained unrun; the logbook has a dated addendum.
  `epicormic_lab.exp_c_analysis` implements the test for the future runner.

- The vocabulary scan reports malformed Python on Python 3.10 and 3.11,
  where the tokenizer emits error tokens instead of raising; before this
  such a file passed the scan silently on those versions.
