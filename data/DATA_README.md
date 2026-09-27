# Data

Provenance of every data file in this directory.

- `panels/`: the pinned canary panels used by the experiments, as plain JSON
  in the epicormic panel format. Each panel's `panel_digest`
  (`epicormic panel digest <file>`) is recorded here and in the
  pre-registration that uses it. Panels are inputs, never outputs: a panel
  changes only by a new file with a new digest.
- `checksums.sha256`: SHA-256 of every file under `data/`, verified before
  each run and regenerated only when a data file is added.

No raw observation store lives under `data/`; those stay under
`experiments/*/runs/*/stores/`, ignored by git, and are archived by digest
(README rule 4).

| File | Added | Panel digest | Used by |
| --- | --- | --- | --- |
| (none yet) | | | |
