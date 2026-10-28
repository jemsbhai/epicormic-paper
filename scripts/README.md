# Scripts

Entry points that call `epicormic_lab`; they hold no experiment logic of
their own.

Present:

- `freeze_protocol.py`: prints `digest  path` for each protocol, the SHA-256
  of its canonical JSON, for the logbook and the registry; `--expect DIGEST`
  exits 1 when the protocol on disk no longer matches.
- `snapshot_environment.py`: writes `environment.json` (git commit and dirty
  flag, Python and OS versions, CPU count, memory, GPUs and driver, every
  installed distribution with its version, and whether the pinned releases
  are installed); `--require-pins` exits 1 when they are not. The wheel and
  sdist digests of the two studied releases live in `epicormic_lab.pins`,
  not in the snapshot.

Planned:

- `run_exp_a.py` .. `run_exp_e.py`: `--profile smoke|full`, `--resume`,
  `--run-id`; each copies the frozen protocol into the run directory before
  anything else runs.
- `make_figures.py`: every figure from `analysis/generated/` only.
- `check_manuscript.py`: the vocabulary scan plus citation-key checks against
  `paper/references/verified_sources.json`, run before every commit that
  touches `paper/`.
