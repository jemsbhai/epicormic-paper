# Experiments

One directory per experiment, named `exp_<letter>_<topic>`:

```
exp_a_calibration/
  PREREGISTRATION.md   hypotheses, design grid, seeds, scorer set, pinned versions, analysis plan,
                       falsification conditions, exact commands; prose for a reader
  protocol.json        the same design, machine-readable; frozen by its SHA-256 digest
  runs/<run_id>/       one directory per run: protocol.frozen.json, manifest.json, environment.json,
                       seed.json (committed) and stores/ with the raw pollard stores (ignored)
```

The protocol digest is computed by `scripts/freeze_protocol.py` over the
canonical JSON serialization (sorted keys, no insignificant whitespace,
UTF-8). It is recorded in the logbook plan entry and in every run manifest,
and a run refuses to start when the file on disk no longer matches the
digest it was registered under. A protocol changes only by adding a new,
dated version next to the old one; the registry says which version each run
used.

`run_registry.yaml` is the append-only index of every run, script or
notebook, smoke or full, completed or failed. Its fields are documented at
the top of the file. `experiments/private/` is ignored by git and holds
anything machine-specific that must never be published.
