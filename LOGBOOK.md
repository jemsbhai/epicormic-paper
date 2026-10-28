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

## 2026-10-28 EXP-A planned (mock arm)

Researcher: Muntaser Syed. Type: computational. Status: planned; frozen
when this commit is tagged `exp-a-prereg`.

Question: when nothing has changed, does epicormic 0.1.0 report `drift` no
more often than its declared level alpha = 0.05, per window and over an
EXP-D length sequence of windows?

Hypotheses: H-A1, the probability of a `drift` state for a null window pair
is at most 0.05 in every A1 cell (Holm across the twelve cells; at the first
step 20 or more drift verdicts of 200 falsify); H-A2, the e-process alarms
within 28 null windows in at most 5 percent of replications (16 or more of
200 falsify). Secondary S-A1 to S-A4 are reported with intervals and not
tested. Full statements, falsification conditions, and the expected results
written before the run: `experiments/exp_a_calibration/PREREGISTRATION.md`.

Independent variables: panel size in {8, 24, 64}; samples per probe N in
{5, 10, 20, 40} (A1), 10 (A2), 3 (A3); horizon 1 (A1, A3) or 28 (A2)
current windows against one baseline window.

Dependent variables: verdict `state` and `rule_fired`; per scorer the pooled
statistic, raw and Holm-adjusted p, CUSUM and Page-Hinkley statistics, and
the maximum e-value over the stream; per-probe raw and BH-adjusted p-values.

Controls: `MockProvider(seed=20261028, match_rate=0.9)` with no injected
drift, one analysis configuration (epicormic's defaults with `latency_s`
removed from the scorer set, decision D22), pinned software. Two null
windows of one panel on one deterministic provider are identical unless the
step callable salts the seed per window (measured 2026-10-28: `T = 0`,
`p = 1` for every scorer without the salt); the salt
`100000 * replication + 1000 * window_index` is part of the protocol.

Protocol: `experiments/exp_a_calibration/protocol.json`, version
2026-10-28, digest
`dd7e4356a60b18a9b122a5def9617b761be313f9d7dfa97481e7601a0115210d`
(SHA-256 of the canonical JSON: sorted keys, separators `,` and `:`,
`ensure_ascii` false, UTF-8). Panels `canary-24-v1`
`8f7883e3ce8f937212a9cd396b1ce318a88e13fa1b8a7369b673a05f10cb3a75`,
`mock-08-v1`
`fe9b9078262c469e0f936a21876309ed38a34d5c7f6466c08db5e32660a2c43c`,
`mock-64-v1`
`c9a567a90e381c57dd0502fa132c11af396d9ccf8ffb0ca696af8905da9946ab`.
Full profile: 4,274,880 observation nodes and 8,020 verdicts; smoke profile
3, 2 and 2 replications per cell for A1, A2 and A3.

Environment: CPU only; recorded per run in `environment.json`. Pilot timing
on 2026-10-28 (not evidence): 1.20 s per replication at panel 24, N = 10,
three scorers, in-memory store, one core, two windows of 240 observations
plus one verdict with 2000 permutations.

Seeds: master 20261028 (provider), analysis seed 0, window salt as above;
`seed.json` per run.

Control arm: design and sizing rule pre-registered in section 9 of the
pre-registration; `protocol.control.json` and its own plan entry follow the
throughput measurement of `HANDOFF.md` section 6.2.

Runs: none yet. Result entries will cite run ids `exp-a-smoke-001` and
`exp-a-full-001`.
