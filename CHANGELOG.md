# Changelog

All notable changes to this repository are recorded here in the Keep a
Changelog format. Experiment runs are recorded in `LOGBOOK.md` and
`experiments/run_registry.yaml`, not here.

## Unreleased

### Added

- `data/panels/canary-24-v2.json`, the hosted panel variant for EXP-D:
  the 24 probes, seed settings and 200-token output cap of `canary-24-v1`
  with the `temperature` key removed from the sampling block (digest
  `aaba1761326e89fe3f6b27521a55d4b56fb2fee87d05400cdeab88ea0bc18fac`),
  because the current cheap tiers disagree about the parameter: Anthropic
  models released after Claude Opus 4.6 reject any value other than 1.0 and
  OpenAI's `gpt-5-nano-2025-08-07` rejects it outright, so a declared
  snapshot switch cannot hold a 0.7 request fixed. `DATA_README.md`
  records the provenance; `checksums.sha256` gains the file; tests pin the
  digest, that v2 differs from v1 only in `name` and `sampling`, and that
  the checksum file matches every panel file.
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
- EXP-C runner and analysis: `epicormic_lab.exp_c` (cells over kind, level
  and quiet length in the protocol's execution order, chains through
  `epicormic_lab.chains`, the recompute check, per-cell zipped stores with
  their digests in the summary, manifest and registry, gzip-compressed cell
  summaries, resume at the cell boundary, the full-profile wall-clock
  projection of the sizing rule) and `epicormic_lab.exp_c_summary` (the
  shared-window check, every detector and the state machine per cell,
  H-C1 over the eligible chains with Holm, H-C2 through
  `exp_c_analysis.summarize_h_c2` with the quiet-length table, S-C1 to
  S-C6 including the offline CUSUM and Page-Hinkley grid with its rounding
  check, the EXP-D export and a provenance block), with
  `scripts/run_exp_c.py`, `scripts/analyze_exp_c.py` and tests at 100
  percent line coverage.
- EXP-C pre-registration (mock arm): `experiments/exp_c_sequential/` with
  `PREREGISTRATION.md`, `protocol.json` (version 2026-10-29), the logbook
  plan entry, and the sizing pilot `pilot/pilot-seed7.json`. In support:
  `epicormic_lab.providers` gains the five drift kinds
  (`drifted_provider`) and the request-hash `mixture` that grades the tool
  swap and the length padding; `epicormic_lab.chains` observes and analyses
  change-point chains and reduces them to first alarms, delays and realised
  effects; `scripts/pilot_exp_c.py` runs the pilot.

### Changed

- EXP-C protocol 2026-11-09-r4 applies the pre-registered sizing rule
  after the registered smoke run `exp-c-smoke-001` projected the full
  profile at 14.2 hours wall-clock at 8 workers: full replications become
  60 (C1), 30 (C2) and 30 (C3), with the planned n, critical counts and
  power of H-C1, the S-C3 denominators, the C3 sample taken from the C1
  cells, R of section 5.1 and the size figures restated for those counts
  and the store sizes recorded as measured (about 1.6 KB per node, 4.2 to
  4.4 to one zipped). r3 is retained as `protocol.2026-11-05-r3.json`,
  run in the smoke profile only; the logbook has a dated addendum; the
  tests pin the r4 digest and the 1800-chain workload. `HANDOFF.md` 7.5
  records the smoke run and gives the full-run command.
- Environment snapshots record physical memory, every installed distribution
  and whether the pins are satisfied; `scripts/snapshot_environment.py
  --require-pins` exits 1 otherwise; a run refuses a protocol whose software
  block does not name the pinned releases (folded in from the local work of
  2026-10-01).
- Pins move to epicormic 0.2.0 (tag `v0.2.0` at
  `40bd810881bc6b4a646b1c79f777b2a42a9fe190`, PyPI wheel and sdist digests
  in `pins.py`), which corrects the e-process null (D27) and replaced 0.1.0
  before any registered run. EXP-A protocol version 2026-10-28-r2
  (`protocol.2026-10-28-r2.json`) pins it and restates H-A2 against the
  threshold in force; version 2026-10-28 stays in place unrun, with a dated
  logbook addendum. `HANDOFF.md` carries the regenerated locked output and
  the new digest; `scripts/run_exp_a.py` defaults to the current protocol.

### Fixed

- EXP-C protocol 2026-11-05-r3 defines the state machine's delay as the
  first `drift` verdict at or after the change (the pooled-test convention)
  and a chain's eligibility for it as the absence of a sticky pre-change
  alarm, so that transient pooled false alarms in the quiet windows no
  longer remove a detected chain from H-C1 and the EXP-D export; it adds
  the state machine's own pre-change false alarm row, the e-process warning
  crossing, the sizing projection, the shared-window check, the S-C5
  rounding check and gzip-compressed per-cell summaries. r2 is retained
  unrun as `protocol.2026-10-30-r2.json`; the logbook has a dated addendum.
  `epicormic_lab.chains.first_alarms` gains the matching fields without
  changing the meaning of the existing ones.
- EXP-C protocol 2026-10-30-r2 preserves shared baseline seeds and tests
  H-C2 by an exact paired three-window threshold test, with Holm across
  levels. It defines the restricted-delay endpoint, whole-pair exclusions
  for pre-change alarms, censoring, ties and incomplete-data checks. The
  original protocol is retained unrun; the logbook has a dated addendum.
  `epicormic_lab.exp_c_analysis` implements the test for the future runner.

- The vocabulary scan reports malformed Python on Python 3.10 and 3.11,
  where the tokenizer emits error tokens instead of raising; before this
  such a file passed the scan silently on those versions.
