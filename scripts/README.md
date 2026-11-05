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
- `pilot_exp_c.py --out PATH [--seed 7] [--reps 10] [--permutations 200]
  [--kinds ...] [--levels ...] [--workers N]`: the EXP-C sizing pilot, one
  JSON document of first-alarm summaries per chain over the drift kinds and
  levels; sizing only, never evidence, and run on its own provider seed.
- `run_exp_c.py --profile smoke|full --run-id ID --digest HEX [--workers N]
  [--resume] [--allow-dirty] [--cells ...]`: runs the EXP-C mock arm from
  the frozen protocol (`--protocol` defaults to `protocol.json`, the version
  in force). Same refusals as `run_exp_a.py`. One cell is one drift kind,
  level and quiet length; each replication is a chain (baseline, quiet
  windows from the null mock, post-change windows from the drifted mock)
  analysed in window order and recomputed. When a cell completes its store
  is zipped under `runs/<run_id>/stores/<cell>.zip`, the zip's SHA-256 goes
  into the summary, the manifest and the registry, and the uncompressed
  store is removed; the cell summary with every chain's verdict records and
  first-alarm reduction is written gzip-compressed as
  `runs/<run_id>/cells/<cell>.json.gz`. `--resume` keeps cells whose summary
  and archive are intact. After a smoke run the script prints the projected
  full-profile wall-clock at `--workers` for the sizing rule.
- `analyze_exp_c.py RUN_DIR [--exp-a-run EXP_A_RUN_DIR]`: writes
  `analysis/generated/exp_c_<run_id>.json` from the cell summaries: the
  shared-window check, per cell every detector and the state machine, H-C1,
  H-C2 (through `epicormic_lab.exp_c_analysis.summarize_h_c2`), S-C1 to
  S-C6 and the EXP-D export, with a provenance block that says whether the
  run can be confirmatory. `--exp-a-run` supplies the EXP-A A2 chains to
  the S-C5 recalibration grid; without it the recommendation is withheld.

Planned:

- `run_exp_b.py`, `run_exp_d.py`, `run_exp_e.py`, and `run_exp_a_control.py`
  for the control arm once `protocol.control.json` is frozen.
- `make_figures.py`: every figure from `analysis/generated/` only.
- `check_manuscript.py`: the vocabulary scan plus citation-key checks against
  `paper/references/verified_sources.json`, run before every commit that
  touches `paper/`.
