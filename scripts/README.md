# Scripts

Entry points that call `epicormic_lab`; they hold no experiment logic of
their own.

Present:

- `freeze_protocol.py PROTOCOL [--expect HEX]`: prints the SHA-256 digest of
  a protocol's canonical JSON (keys sorted, no insignificant whitespace,
  `ensure_ascii` false, UTF-8), for the logbook and the registry; with
  `--expect` it exits 1 when the file no longer matches.
- `snapshot_environment.py [--out PATH] [--require-pins]`: writes or prints
  `environment.json` (git commit and dirty flag, Python and OS, CPU count and
  memory, GPU and driver when `nvidia-smi` answers, installed package
  versions and every installed distribution, the release pins and whether
  they are satisfied); `--require-pins` exits 1 when they are not.
- `run_exp_a.py --profile smoke|full --run-id ID --digest HEX [--workers N]
  [--resume] [--allow-dirty] [--cells ...]`: runs the EXP-A mock arm from the
  frozen protocol (`--protocol` defaults to the current version,
  `protocol.2026-10-28-r2.json`). The run refuses to start when the protocol digest differs
  from `--digest`, when a pinned package is not the installed one, or (full
  profile) when the tree is dirty; it writes the run directory
  (`protocol.frozen.json`, `environment.json`, `seed.json`, `manifest.json`,
  `cells/*.json`, the ignored `stores/`) and appends the registry entry when
  every cell completes. `--resume` keeps cells that have a summary and reruns
  the rest from their first replication.
- `analyze_exp_a.py RUN_DIR`: writes `analysis/generated/exp_a_<run_id>.json`
  from the cell summaries of a run directory.

Planned:

- `run_exp_b.py` .. `run_exp_e.py`, `run_exp_a_control.py` for the control
  arm once `protocol.control.json` is frozen.
- `make_figures.py`: every figure from `analysis/generated/` only.
- `check_manuscript.py`: the vocabulary scan plus citation-key checks against
  `paper/references/verified_sources.json`, run before every commit that
  touches `paper/`.
