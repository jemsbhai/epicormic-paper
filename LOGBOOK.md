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

## 2026-10-28 EXP-A plan addendum: protocol version 2026-10-28-r2

Addendum to the entry "2026-10-28 EXP-A planned (mock arm)" above, which
stays as written. No run of version 2026-10-28 was registered.

Reason: a development smoke run of the runner (scratch copy, not
registered, not evidence) on the real protocol showed a deterministic
false alarm of epicormic 0.1.0's e-process. `refusal` and `truncated` are
constant 0 on the mock; the plug-in null rate was clipped to 0.0021; the
downward bettor accumulated that gap and crossed the threshold inside
window 13 of the 28-window A2 chain, with an identical e-value trajectory
in both smoke replications (0.62 after window 1, 10.5 at window 11, 20.6
at window 13, 4750 at window 28). `output_chars` did the same through its
sign stream. The same mechanism applies, more slowly, to any estimated
rate. epicormic 0.2.0 (D27, released 2026-10-28, tag v0.2.0 at
`40bd810881bc6b4a646b1c79f777b2a42a9fe190`) replaces the clipped point
null with the baseline's exact binomial interval at confidence
1 - alpha/2 and alarms at 2/alpha; its test suite reproduces the window 13
alarm with the old null and its absence with the new one.

Change: `experiments/exp_a_calibration/protocol.2026-10-28-r2.json`,
digest `5934acb50e9d4f9403bb64cd038cf492bcd167d7464eef8a1fdd24da2e555de4`, pins
epicormic 0.2.0, restates H-A2 and its falsification condition against the
threshold in force, and adds the interval behind the null to the reports.
Panels, cells, replication counts, analysis configuration, seeds, and
procedure are unchanged; the config digest is unchanged. `protocol.json`
(version 2026-10-28, digest `dd7e4356a60b18a9b122a5def9617b761be313f9d7dfa97481e7601a0115210d`)
stays in place unrun. The repository pins move to epicormic 0.2.0
(`src/epicormic_lab/pins.py`, wheel
`15c0051d97275dc5434e2abf353cb8b9e25f249f284ba1c36355e39b00abd3a0`, sdist
`1530fad6dfdad0545c15f3ad14cf0b27c7d0075bf9614b57bc2b189f67334ad5`).
Frozen when this commit is tagged `exp-a-prereg-r2`.

Pilot timing from the development smoke run, for sizing only: observations
2.4 to 3.1 ms each; verdicts 0.7 s at panel 8 by N 5, 3.9 s at 24 by 10,
14.7 s at 24 by 40, about 40 s at 64 by 40, each recomputed once;
projected full profile about 23 CPU-hours on a slow two-core machine, the
A2 cell about 10 hours of it.

## 2026-10-29 EXP-C planned (mock arm)

Researcher: Muntaser Syed. Type: computational. Status: planned; frozen
when this commit is tagged `exp-c-prereg`.

Question: when the provider changes at a known window, how many windows
pass before each epicormic 0.2.0 detector alarms (the pooled test, CUSUM,
Page-Hinkley, the e-process, and the state machine's first `drift`), by
drift kind and level, by samples per probe, and by the number of quiet
windows before the change; and how many alarms do the quiet windows
produce?

Hypotheses: H-C1, at panel 24 and N 10 with 14 quiet windows, for every
drift kind at every level in {0.2, 0.3, 0.5} the state machine reports
`drift` within 2 windows of the change in at least 90 percent of chains
(exact one-sided binomial per cell against 0.90, Holm across the 15 cells;
at the first step 80 or fewer detections of 100 falsify); H-C2, the
e-process delay grows with the quiet length: for the match kind at levels
0.3 and 0.5, the delay with 28 quiet windows is stochastically larger than
with 0, by at least 3 windows at the median (one-sided Mann-Whitney U per
level, Holm across the two). Secondary S-C1 to S-C6 (realised effect per
scorer, delay of every detector and scorer, pre-change false alarms,
window size, offline recalibration grid for CUSUM and Page-Hinkley, the
e-value at the change) are reported with intervals and not tested. Full
statements, falsification conditions, the export to EXP-D and the expected
results written before the run:
`experiments/exp_c_sequential/PREREGISTRATION.md`.

Independent variables: drift kind in {match, refusal, truncation,
tool_swap, length} and level in {0.05, 0.1, 0.2, 0.3, 0.5} (C1); N in {5,
20} (C2); quiet windows in {0, 7, 28} with 14 from C1 (C3). Every chain has
one baseline window and 14 post-change windows.

Dependent variables: per verdict as in EXP-A; per chain the first alarm
window, pre-change flag and delay of every detector and scorer, the first
`drift` verdict and its rule, the realised effect per scorer, the e-value
before the change (`epicormic_lab.chains.first_alarms`).

Controls: `MockProvider(seed=20261029, match_rate=0.9)` as the null; the
drifted mock keeps the seed (common random numbers); the window salt of
EXP-A, which also makes every cell at one geometry share its quiet windows
with every other at the same replication index; one analysis
configuration, identical to EXP-A r2; pinned software. The mixture kinds
route by a hash of the whole request, never by the seed alone, because the
panel gives every probe the seed `seed_base + attempt`.

Protocol: `experiments/exp_c_sequential/protocol.json`, version 2026-10-29,
digest `ef5062ae6a7da040e1b4194e79482de6d3d36e61923b12dcda0af7acd5f1124e` (SHA-256 of the canonical JSON: sorted keys,
separators `,` and `:`, `ensure_ascii` false, UTF-8). Panel `canary-24-v1`
`8f7883e3ce8f937212a9cd396b1ce318a88e13fa1b8a7369b673a05f10cb3a75`. Full
profile: 35 cells, 3000 chains, 83,300 verdicts, about 21.1 million
observation nodes (about 40 GB of stores, zipped per cell as they
complete); smoke profile 2 replications per cell.

Environment: CPU only; recorded per run in `environment.json`. Intended
runner: Katie's machine (HANDOFF 7.5); the smoke profile sets the full
replication counts by the 12-hour wall-clock rule of the pre-registration.

Seeds: master 20261029 (provider, null and drifted), analysis seed 0,
window salt as in EXP-A, mixture tag `epicormic-lab/mixture/v1:`;
`seed.json` per run.

Pilot (sizing only, not evidence): `scripts/pilot_exp_c.py` at seed 7, 200
permutations, ten chains per C1 cell, committed as
`experiments/exp_c_sequential/pilot/pilot-seed7.json`
(SHA-256 `619640385544f369e1b6a59c4996fbacde506054abb799986a85811c814cf074`).
Realised effect on the primary scorer within 0.01 of the level for every
kind and level; first `drift` in the first drifted window in 10 of 10
chains at level 0.2 and above for every kind, from the pooled test every
time; e-value of `normalized_match` about 3e-8 after 14 quiet windows and
e-process median delays of 3.5, 6.5 and more than 14 windows at levels 0.5,
0.3 and 0.2 for the match kind; no e-process stream on
`tool_call_set_jaccard` and a degenerate one on `output_chars` (never
alarms on the length kind); CUSUM and Page-Hinkley median delays 4 to 5
windows at level 0.2; no pre-change alarm of any detector in the ten
distinct quiet chains.
Wall-clock of the pilot: about 160 s per ten chains of 29 windows on one
slow core at 200 permutations, in-memory store, no recompute.

Runs: none yet. Result entries will cite run ids `exp-c-smoke-001` and
`exp-c-full-001`.
