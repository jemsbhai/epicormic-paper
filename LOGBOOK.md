# Logbook

Append-only record of every experiment run for the epicormic paper. The plan
entry (hypothesis, independent and dependent variables, controls, protocol,
environment, seeds) is written and committed before a run starts; the result
entry (results, observations, interpretation, artifacts) is appended after it
ends; a correction is a dated addendum that cites the original entry. Nothing
is edited after the fact, and a failed run gets an entry like any other.

Experiment ids follow section 16 of `docs/PLAN.md` in the epicormic
repository: EXP-A calibration, EXP-B power, EXP-C sequential detection delay,
EXP-D longitudinal hosted canary, EXP-E cost and energy of monitoring. Run
ids are `exp-<letter>-<profile>-<nnn>` and are registered in
`experiments/run_registry.yaml`; a logbook entry cites its run id.

Commit convention: `docs(logbook): EXP-X planned`,
`docs(logbook): EXP-X completed`, `docs(logbook): EXP-X failed`.

---
