# Scripts

Entry points that call `epicormic_lab`; they hold no experiment logic of
their own. Planned:

- `snapshot_environment.py`: writes `environment.json` (git commit and dirty
  flag, Python and OS versions, CPU, GPU and driver, installed package
  versions with wheel digests where available).
- `freeze_protocol.py`: prints the SHA-256 digest of a protocol's canonical
  JSON, for the logbook and the registry.
- `run_exp_a.py` .. `run_exp_e.py`: `--profile smoke|full`, `--resume`,
  `--run-id`; each copies the frozen protocol into the run directory before
  anything else runs.
- `make_figures.py`: every figure from `analysis/generated/` only.
- `check_manuscript.py`: the vocabulary scan plus citation-key checks against
  `paper/references/verified_sources.json`, run before every commit that
  touches `paper/`.
