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

## 2026-10-30 EXP-C plan addendum: paired finite-horizon inference

Correction to the 2026-10-29 EXP-C plan entry, before freeze or a registered
confirmatory run. Review: PR #8, discussion r4415181305. The PR head inspected
was `27a9f64f4e5e6533ddf618e0f9a3bb8deea8c247`; the finding was unresolved,
there were no later PR commits or replies, and no `exp-c-prereg` tag.
Main had advanced through PR #7 to
`d2e4cf71f9773d7826adabb94599d96c16720586` (environment snapshots and protocol
software checks); these changes were inspected and tested in combination
with this correction in a separate local integration tree.

`observe_chain` salts the baseline by replication and absolute window index
0, regardless of quiet length. C3's 0-quiet and 28-quiet observations share
the baseline; the former's post-change requests also share salts with part
of the latter's quiet period. The post-change streams at equal time since
change are different (absolute indices 1..14 versus 29..42). These are
replication pairs. Preserve this control of baseline variation rather than
introducing independent baseline seeds merely to fit an unpaired test.

H-C2 now tests, separately at levels 0.3 and 0.5, whether more than half of
eligible pairs have Y28 - Y0 >= 3, where Y is the observed delay in 1..14,
or 15 for no alarm within that complete horizon. The value 15 is a bounded
terminal category, not an observed detection or an estimate beyond the
horizon. Exclude a whole pair if either primary e-process alarm preceded
its change and report excluded ids and both arms' counts. This conditional
estimand must be read alongside S-C3. All other pairs, including tied and
censored pairs, remain in the denominator. Missing partners, duplicate
ids, inconsistent outcomes or incomplete horizons stop analysis.

The test is an exact binomial upper tail for k = count(Y28 - Y0 >= 3),
null probability 0.5, alternative greater, with Holm across both levels.
Exactly 3 is a success; differences below 3 are failures. With no eligible
pairs, p = 1 and the estimate and interval are null. Both adjusted p-values
must be at most 0.05. Non-rejection means not supported, not evidence of no
penalty. The sample median of within-pair restricted differences replaces
the former Hodges-Lehmann language; stochastic dominance, an uncensored
median shift, and linear growth are not claimed by this test. Delay
quantiles beyond the observation horizon stay "above 14"; a median slope
is not computed if any required median is censored.

Current protocol: `experiments/exp_c_sequential/protocol.json`, version
2026-10-30-r2, canonical digest
`d176f31ebc77cc9f28e5dcbefcca77e88f31fbea16c300cb9ebd2c1aac2eda4f`.
Original version retained verbatim as `protocol.2026-10-29.json`, digest
`ef5062ae6a7da040e1b4194e79482de6d3d36e61923b12dcda0af7acd5f1124e`.
The cells, seeds, replication counts, detector configuration and pinned
releases have not changed. The seed-7 pilot and its committed artifact are
unchanged exploratory design input; no confirmatory observations were
collected or analysed for this correction.

Implementation: `epicormic_lab.exp_c_analysis.summarize_h_c2`, for the future
EXP-C runner and full-run analysis. Regression tests capture actual salted
requests and mock responses through `observe_chain`; check matching by id,
pre-change alarms, censoring, ties, empty eligibility and missing partners;
check every success count at n = 1, 7, 30 and 50 against SciPy's exact
binomial test; and require the protocol to match the executable analysis.

Validation on Linux, Python 3.12.14, epicormic 0.2.0 and pollard 1.6.0:
84 tests pass with 100 percent line coverage on the PR branch; 87 tests
pass with 100 percent coverage when combined with current main. Ruff,
strict mypy and the vocabulary scan pass on both trees. The canonical
protocol digest check passes. These are software checks, not EXP-C results;
no full experiment was run. Resolve the review finding after this correction
is committed; freeze only the reviewed, checked version with `exp-c-prereg`
on the merge commit. The experiment runner still follows separately.

## 2026-11-05 EXP-C plan addendum: state-machine delay, eligibility, summaries

Correction to the 2026-10-29 EXP-C plan entry and its 2026-10-30 addendum,
before any run. Version 2026-10-30-r2 was frozen at tag `exp-c-prereg`
(merge commit `89bef42a23978df46230bbec647f7edebd0d8da0`, 2026-10-31) and
stays in place unrun; no smoke or full run exists, and no observations were
collected for this correction. The runner was being written against r2 when
the gap below was found.

Gap: r2 left the state machine's delay to the sticky convention of
`epicormic_lab.chains.first_alarms`, under which any `drift` verdict before
the change removes the chain's state delay, and H-C1 counted chains with a
state delay of at most 2 "out of 100". A pre-change rejection of the pooled
test is a transient per-window false alarm: the state returns to stable or
warning in the next window and the change is still detected at the change
window. The pooled test after Holm across the seven scorers is expected to
reject a quiet window at a rate near alpha (EXP-A H-A1 measures it), and
over 14 quiet windows that compounds to a fraction of chains that the ten
pilot chains cannot bound; by the window salt those chains are the same set
in every C1 cell. Under the literal reading H-C1 would have been decided by
pre-change false alarms rather than by delays, and the EXP-D export (D90
over all chains) would have been "above 14" for the same reason. Only the
sticky detectors (e-process, CUSUM, Page-Hinkley) keep the state at
`drift` from a pre-change alarm onward.

Change: `experiments/exp_c_sequential/protocol.json`, version
2026-11-05-r3, canonical digest
`ed87bebb3c1bc9aa200c5196a231ed03c7dd34e9fe79739efac3b73d90725ea5`. The
superseded r2 is retained verbatim as `protocol.2026-10-30-r2.json`, digest
`d176f31ebc77cc9f28e5dcbefcca77e88f31fbea16c300cb9ebd2c1aac2eda4f`, and
the original 2026-10-29 as before. r3 defines: the state delay as the first
`drift` verdict at or after the change (the pooled-test convention; the
first `warning` or `drift` likewise); eligibility for a state delay as the
absence of a sticky pre-change alarm on any configured scorer, with the
ineligible replication ids reported per cell; the state machine's own row
in S-C3 (a `drift` verdict before the change with the rule of the first
one, and the sticky pre-change rate, which is the ineligibility rate); the
e-process warning crossing as the first window whose running maximum
e-value reached half the threshold; the sizing projection as the makespan
of the full cells dispatched in execution order to the runner's worker
count; the shared-window check (the pre-change verdict records of every
cell at one geometry must agree replication by replication over the quiet
windows they have in common, and S-C3 counts distinct chains once); the
S-C5 rounding check (the rerun at the shipped defaults over the recorded
six-significant-digit T series must reproduce the recorded alarms, and the
A2 recommendation is withheld without the EXP-A run); and the per-cell
summaries as gzip-compressed JSON, `cells/<cell>.json.gz`, because the
full profile's 83,300 verdict records are about 280 MB uncompressed. H-C1
now tests the count of eligible chains with a state delay of at most 2
against p0 = 0.90 over the n eligible chains of the cell (planned 100, n
reported), same exact binomial, same Holm family of 15, same first-step
critical count of 80 and powers 0.54 and 0.90 at n = 100, with the critical
count and power at the realised n reported, and the unconditional count out
of all chains reported descriptively. The EXP-D bound becomes conditional
on the monitor carrying no sticky alarm into the switch, with the S-C3
sticky rate exported beside it. Cells, panel, seeds, replication counts,
detector configuration, H-C2 and the pinned releases are unchanged; the
analysis config digest is unchanged.

Implementation: `first_alarms` gains the fields `pre_change_drift_windows`,
`pre_change_sticky`, `eligible`, `first_drift_at_or_after_change`,
`first_warning_at_or_after_change` and `state_delay` in its state block and
`warning_first` per e-process entry, without changing the meaning of any
existing field, so the committed pilot artifact keeps its meaning. Tests
cover the transient pooled false alarm, the sticky pre-change alarm, the
chain without quiet windows, and the warning crossing.

Validation: the four checks pass on the branch (Linux, Python 3.13.18,
epicormic 0.2.0 and pollard 1.6.0; CI on Ubuntu and Windows with 3.10 and
3.12). Frozen when the merge commit of this change is tagged
`exp-c-prereg-r3`. The runner and the analysis follow in their own pull
request and read r3.

## 2026-11-08 EXP-C smoke run exp-c-smoke-001 completed

Researcher: Katherine Burge. Type: computational. Status: completed;
smoke profile, an instrumentation check and not evidence.

Run: `exp-c-smoke-001` at commit `d009c53`, protocol version 2026-11-05-r3
(digest `ed87bebb...ea5`), epicormic 0.2.0 and pollard 1.6.0, started
2026-11-08T00:22Z and finished 00:44Z. Machine: Apple M1 Pro, 8 cores,
16 GB RAM, macOS 27.0.1, Python 3.14.7, `--workers 8`.

Result: all 35 cells completed at two replications each (70 chains, 1,932
verdicts). The runner's projection for the full profile at 8 workers is
14.2 h wall-clock (makespan), 105.1 CPU-hours, longest cell 3.8 h; within
12 hours: no. Per the 12-hour rule in the pre-registration, the
replication counts are for Muntaser to set in a new protocol version. The
35 timing lines are posted in the `EXP-B and EXP-C` issue.

Stores: 35 zip archives, one per cell, with SHA-256 digests recorded by
the runner in `store_digests`; kept outside git. Free disk on this machine
is 16 GB, below the about 50 GB the full profile needs at 8 workers.

## 2026-11-09 EXP-C plan addendum: replication counts by the sizing rule

Protocol version 2026-11-09-r4, written after the registered smoke run
`exp-c-smoke-001` and before any full run. Version 2026-11-05-r3 was frozen
at tag `exp-c-prereg-r3` (commit `739b5961d7085fae909521a903f624c38bc70e1c`)
and was run in the smoke profile only; it stays in place verbatim as
`protocol.2026-11-05-r3.json`, digest
`ed87bebb3c1bc9aa200c5196a231ed03c7dd34e9fe79739efac3b73d90725ea5`, and
versions r2 and r1 stay as before, unrun.

Reason: the sizing rule of section 4, item 2 of the pre-registration (in
`run.sizing` of every version since r1): if the smoke timing projects a
full-profile wall-clock above 12 hours at the runner's worker count, a new
dated version lowers C1 to 60 and C2 and C3 to 30 replications before the
full run, never after it. The smoke run on Katie's Apple M1 Pro (8 cores,
`--workers 8`) measured 3.6 to 6.0 s per verdict (about 4.1 s in the C1
cells) and the runner projected the full profile at the r3 counts of 100,
50 and 50 replications at 14.2 h wall-clock (makespan), 105.1 CPU-hours
and a longest cell of 3.8 h (`within_12_hours: no`). The rule fires, and
r4 is its application; no judgement about the counts was exercised after
seeing the timing. The decision of the 2026-11-08 result entry, that the
counts are for Muntaser to set, is resolved by the rule, which names them.

Change: `experiments/exp_c_sequential/protocol.json`, version
2026-11-09-r4, canonical digest
`aeb4cc1e53ea0cd543ea049d70dbb890fbe537aa148410f94e99511dee8027c0`. Full
replications 60 (C1), 30 (C2), 30 (C3); the C3 point at 14 quiet windows
is the first 30 replications of the C1 cell of the same kind and level; the
smoke profile stays at two replications per cell, so `exp-c-smoke-001`
remains the instrumentation check for the full run. Restated for the new
counts: H-C1 tests the count of eligible chains with a state delay of at
most 2 against p0 = 0.90 over the n eligible chains (planned 60, n
reported); the same exact binomial, the same Holm family of 15 at 0.05;
first-step critical count 46 or fewer of 60 (was 80 of 100), unadjusted
flag 49 or fewer of 60 (was 84 of 100); power at the first step 0.31
against a true rate of 0.80, 0.67 against 0.75 and 0.90 against 0.70 (was
0.54 against 0.80 and 0.90 against 0.75), with the critical count and
power at the realised n still reported with the result. The S-C3
denominators become 60 distinct chains of 14 quiet windows at panel 24 by
N 10, 30 of 28 quiet windows, 30 of 14 at N 5 and 30 at N 20; H-C2 keeps
its exact paired threshold test with R = 30 planned pairs per level (first
Holm step rejects at 21 or more of 30 with the penalty; power 0.59 at a
true pair probability of 0.7, 0.94 at 0.8). Full profile: 35 cells, 1800
chains, 49,980 verdicts, about 12.6 million observation nodes (was 3000,
83,300 and 21.1 million). Cells, geometry, seeds, drift kinds and levels,
detectors, the analysis configuration (config digest unchanged),
hypotheses, tests, the export to EXP-D and the pinned releases are
unchanged.

Sizes, measured rather than estimated: the C1 smoke stores are 11.2 to
11.3 MB of SQLite per replication (about 1.6 KB per observation node) and
zip at 4.2 to 4.4 to one, so a C1 cell at 60 replications is about 0.7 GB
uncompressed and 0.16 GB zipped and the full profile about 20 GB
uncompressed and 4.6 GB zipped; the per-cell summaries are about 170 MB
uncompressed. Projection at the r4 counts, by the runner's rule over the
smoke timings: 8.5 h wall-clock, 63.0 CPU-hours, longest cell 2.3 h at 8
workers (16.5 h at 4 workers), and at most about 8.5 GB on disk at once at
8 workers (finished zips plus up to eight live stores). The 2026-11-08
result entry's figure of about 50 GB was the r1 to r3 estimate of the
uncompressed total; with cell-by-cell compression the 16 GB free on the
smoke machine is enough for the full profile at the r4 counts.

Validation: the four checks pass on the branch (Linux, Python 3.13.18,
epicormic 0.2.0 and pollard 1.6.0, coverage 100 percent; CI on Ubuntu and
Windows with 3.10 and 3.12 confirms before the merge); the test suite pins
the r4 digest and the 1800-chain workload, keeps the r3, r2 and r1
digests, checks that r4 differs from r3 only in the full replication
counts, and runs the synthetic summary grid at the r4 counts. Frozen when
the merge commit of this change is tagged `exp-c-prereg-r4`. The
runner code is unchanged since `d009c53`, so the same merge commit carries
the `exp-c-frozen` tag of section 10, and the full run starts from a clean
tree at that commit with `--profile full`, a new run id and the r4 digest,
only when Muntaser says so.

## 2026-11-08 EXP-A smoke run exp-a-smoke-001 completed

Researcher: Michael Friedberg. Type: computational. Status: completed;
smoke profile of the mock arm, an instrumentation check and not evidence.

Run: `exp-a-smoke-001` at commit `b3e175e` (main, clean tree), protocol
version 2026-10-28-r2 (digest `5934acb5...5de4`), epicormic 0.2.0 and
pollard 1.6.0, started 2026-11-08T22:33Z and finished 22:36Z. The commit
is later than the tag `exp-a-prereg-r2` (`4773b26`); between the two, the
only change to the EXP-A runner is the protocol software check added to
`run_experiment`, and the other changes add EXP-C and extend the
environment snapshot. Machine: AMD Ryzen 9 5950X, 16 cores and 32
threads, 60 GB RAM, Ubuntu 26.04.1, Python 3.14.4, `--workers 16`.

Result: all 14 cells completed (12 A1 cells at three replications, A2 and
A3), 57,408 observations and 94 verdicts, each verdict recomputed once,
in 2 min 38 s wall-clock. The longest cell is A2-p24-n10 at 158.0 s for
13,920 observations and 56 verdicts. The analysis wrote
`analysis/generated/exp_a_exp-a-smoke-001.json`: pooled A1 drift 0 of 36
(95 percent upper bound 0.097), no A1 cell falsified after Holm,
and every A3 verdict `unknown`. The 14 timing lines are posted in the
`EXP-A and the control` issue.

Stores: 14 SQLite stores, 82 MB, with SHA-256 digests recorded by the
runner in `store_digests`; kept outside git, and the zip with its digest
goes to Muntaser separately.
