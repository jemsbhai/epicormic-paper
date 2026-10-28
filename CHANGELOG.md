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
- `epicormic_lab.protocol`: canonical JSON serialization (sorted keys, no
  insignificant whitespace, UTF-8, no NaN) and SHA-256 digests of protocols;
  validation of the four required keys (`experiment`, a dated `version`,
  and `epicormic` and `pollard` equal to the pins); loading and digest
  verification; and the `freeze_protocol` command with `--expect`.
- `epicormic_lab.environment`: the environment snapshot every run manifest
  records (git commit and dirty flag, interpreter, platform, CPU count,
  memory, GPUs and driver through nvidia-smi, every installed distribution,
  pin status) and the `snapshot_environment` command with `--output` and
  `--require-pins`.
- `scripts/freeze_protocol.py` and `scripts/snapshot_environment.py` as thin
  front-ends over the package.

### Changed

- Lab package version 0.0.2. `psutil` is a dependency (memory and CPU count
  without platform-specific code) and `types-psutil` joins the `dev` extra
  for strict mypy.

### Fixed

- The vocabulary scan reports malformed Python on Python 3.10 and 3.11,
  where the tokenizer emits error tokens instead of raising; before this
  such a file passed the scan silently on those versions.
