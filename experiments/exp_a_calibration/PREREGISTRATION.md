# EXP-A pre-registration: calibration under the null of no provider change

| Field | Value |
| --- | --- |
| Experiment | EXP-A (section 16 of the epicormic `docs/PLAN.md`) |
| Protocol | `protocol.json`, version 2026-10-28, mock arm |
| Protocol digest | `dd7e4356a60b18a9b122a5def9617b761be313f9d7dfa97481e7601a0115210d` |
| Software under study | epicormic 0.1.0 on pollard 1.6.0, pinned in `src/epicormic_lab/pins.py` |
| Panels | `canary-24-v1` `8f7883e3ce8f937212a9cd396b1ce318a88e13fa1b8a7369b673a05f10cb3a75`; `mock-08-v1` `fe9b9078262c469e0f936a21876309ed38a34d5c7f6466c08db5e32660a2c43c`; `mock-64-v1` `c9a567a90e381c57dd0502fa132c11af396d9ccf8ffb0ca696af8905da9946ab` |
| Arms | Mock arm (this protocol); local control arm (`protocol.control.json`, frozen separately, section 9) |
| Status | Frozen when the commit carrying this file and the logbook plan entry is tagged `exp-a-prereg`; until then a draft |

The protocol digest is SHA-256 over the canonical JSON of `protocol.json`:
keys sorted, separators `,` and `:` with no whitespace, `ensure_ascii`
false, UTF-8. `scripts/freeze_protocol.py` computes exactly this; the run
manifest records it, and a run refuses to start when the file on disk no
longer matches.

## 1. Question

epicormic reports one of four states for a current window of canary
observations against a baseline window: `unknown`, `drift`, `warning`,
`stable`. The `drift` state fires when a pooled per-scorer test rejects
after Holm at alpha, or when a sequential detector alarms. EXP-A asks
whether, when nothing has changed, the detector reports `drift` no more
often than its declared level. Everything else in the paper (power in EXP-B,
detection delay in EXP-C, the hosted canary in EXP-D) is interpretable only
if this holds, so EXP-A runs first and its result gates the others.

Two arms test two different nulls:

- The mock arm uses epicormic's seeded `MockProvider` with no injected
  drift. Its behaviour is a known, exchangeable sampling process, so the
  arm tests the statistics alone, at scale and at zero cost. This document
  pre-registers the mock arm in full.
- The control arm uses the locally pinned model of epicormic decision D11
  (llama.cpp `b9630` serving the Qwen2.5-Coder 7B GGUF whose SHA-256 is
  `60e05f2100071479f596b964f89f510f057ce397ea22f2833a0cfe029bfc2463`,
  see `HANDOFF.md` section 6). Its null is "the whole system, model and
  server and adapter and epicormic, run twice on the same pinned model".
  Section 9 pre-registers its design and the rule that sizes it; its
  replication counts are filled from the measured throughput and frozen in
  `protocol.control.json` before any control run.

## 2. Hypotheses

Let alpha = 0.05 be the configured level. A replication is one baseline
window plus one or more current windows drawn under the null, analysed
exactly as epicormic analyses them.

Primary, confirmatory:

- H-A1 (window verdict). In every A1 cell (panel size in {8, 24, 64} by
  N in {5, 10, 20, 40}), the probability that a null window pair receives
  the state `drift` is at most alpha. With 200 replications per cell the
  drift count is tested against p0 = 0.05 by the exact one-sided binomial
  test; the twelve per-cell p-values are Holm-adjusted at family level 0.05.
  A cell whose adjusted p-value is at or below 0.05 falsifies H-A1 for that
  cell. At the first Holm step that is 20 or more drift verdicts of 200;
  the unadjusted per-cell flag, 16 or more of 200, is reported as
  descriptive. Under a true rate of exactly 0.05 the unadjusted flag fires
  by chance in 4.4 percent of cells, so an isolated unadjusted flag is not
  a falsification; the Holm rule is.
- H-A2 (anytime-valid detector). In the A2 cell (panel 24, N = 10, 28
  consecutive null windows against one baseline window, the EXP-D
  geometry), the probability that the betting e-process reaches 1/alpha at
  any observation within the 28 windows is at most alpha, for each scorer
  and for the union over scorers. The union count of 200 is tested by the
  exact one-sided binomial test at level 0.05: 16 or more falsifies. Per
  Ville's inequality the bound is exact only when the plug-in baseline rate
  equals the true rate; here the baseline is 10 samples per probe pooled
  over 24 probes, so a falsification is a statement about that baseline
  size, see section 7.

Secondary, reported and not tested:

- S-A1. Raw pooled p-values per scorer are uniform under the null: the
  empirical fraction at or below 0.01, 0.05, 0.10 and 0.50 with
  Clopper-Pearson intervals, and the Kolmogorov-Smirnov distance to the
  uniform distribution, per scorer and cell. At N = 5 the permutation
  distribution is discrete and the test is conservative by construction;
  this is reported, not treated as a defect.
- S-A2. CUSUM and Page-Hinkley false alarm rates at their initial defaults
  (k = 0.1, h = 0.4; delta = 0.05, lambda = 0.5) over 28 null windows, per
  scorer, with the first-alarm window distribution, and the state-level rate
  of any `drift` verdict within 28 windows broken down by `rule_fired`. These
  two detectors are heuristics in epicormic 0.1.0 (PLAN.md section 17) and
  EXP-C calibrates them; EXP-A records their behaviour at the defaults so
  that the EXP-D configuration can be chosen with that number in hand.
- S-A3. With N = 3 every probe is below `n_min` = 5, so every verdict must be
  `unknown` with rule 1 fired. Twenty replications; any other state is a
  defect in the state rules.
- S-A4. The `warning` rate under the null, with the per-probe
  Benjamini-Hochberg path and the sequential half-threshold path separated.

## 3. Design

### 3.1 Null model

`MockProvider(seed=20261028, match_rate=0.9)` with `drift=None`: every
request receives a deterministic answer that equals the probe's canonical
answer with probability 0.9 and a tagged variant otherwise, one tool call
named `lookup`, a `stop` finish reason, and token counts derived from the
text. The randomness of one answer is a hash of the provider seed and the
request, including the request's `seed` field. No sleep is injected, so
`latency_s` on the mock is the microsecond cost of the call itself; it is
excluded from the scorer set, see 3.4.

### 3.2 Independence of windows

A window's samples get `seed = seed_base + attempt` from the panel
(`seed_from_attempt`), and `seed_base` is part of the panel digest, so two
windows of one panel on one deterministic provider receive identical seeds
and are identical: every pooled statistic is exactly 0 with p = 1. Measured
on 2026-10-28 with epicormic 0.1.0 (panel 24, N = 10, same `MockProvider`
instance, two windows): `T = 0`, `p = 1` for every scorer. A calibration
built on such pairs would report a false alarm rate of exactly 0 and
falsify nothing.

The step callable therefore adds a window salt to the request seed before
calling the provider:

```
seed_sent = request["seed"] + 100000 * replication + 1000 * window_index
```

with `window_index` 0 for the baseline window and 1..K for the current
windows. The salt lives in the step callable, outside the pollard identity
payload and outside the panel digest, exactly where pollard's EXP-001 keeps
its sampling parameters. Seeds are disjoint across windows because N is at
most 40 and K + 1 is at most 29. The same mechanism serves the control arm,
where the salted seed is the llama-server `seed`. With the salt, two null
windows are independent draws (measured: `T` and `p` spread as for distinct
provider seeds). The salt formula and every realised seed are written to
`seed.json`.

### 3.3 Variables

Independent: panel size (8, 24, 64) and samples per probe N (5, 10, 20,
40) in A1; the window horizon (28) in A2; N = 3 in A3.

Dependent, per verdict: `state`, `rule_fired`, per scorer the pooled
statistic `T`, raw and Holm-adjusted p, the number of contributing probes,
the fraction of probes with `|delta| >= effect_min`; per scorer the CUSUM
and Page-Hinkley statistics and the maximum e-value over the stream; the
per-probe raw and BH-adjusted p-values (kept to `top_k` = 50 in the verdict
payload and in full in the cell summary).

Held constant: the analysis configuration (3.4), the provider seed and
match rate, the panel for a given size, the absence of injected drift, the
software pins.

### 3.4 Analysis configuration

The `epicormic/config/v1` document in `protocol.json`, which is epicormic's
default configuration with one change: `latency_s` is removed from the
default scorer set. Scorers: `normalized_match`, `exact_match`,
`tool_call_set_jaccard`, `refusal`, `truncated`, `output_chars`,
`output_tokens`. alpha 0.05, q 0.05, 2000 permutations, analysis seed 0,
`n_min` 5, `effect_min` 0.2, `unknown_fraction` 0.5, `top_k` 50, sequential
defaults as shipped. The removal follows epicormic decision D22 and PLAN.md
section 17: the e-process has no effect-size floor, and on the mock the
microsecond timings shift systematically between runs, so `latency_s` would
measure the host, not the detector. Measured on 2026-10-28: the default set
with `latency_s` reports `drift (pooled test rejected for latency_s)` on a
null pair of mock windows. On the mock, `refusal` and `truncated` are
constant 0 and `tool_call_set_jaccard` is constant 1, so they never reject;
they stay in the set because Holm is applied across the configured scorers
and the paper reports the detector as configured.

The monitor configuration is identical in every cell, so the config digest
is one value, recorded in the run manifest.

### 3.5 Cells and replications

| Part | Panel sizes | N | Baseline windows | Current windows | Replications (full) | Replications (smoke) |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | 8, 24, 64 | 5, 10, 20, 40 | 1 | 1 | 200 per cell (12 cells) | 3 |
| A2 | 24 | 10 | 1 | 28 | 200 | 2 |
| A3 | 24 | 3 | 1 | 1 | 20 | 2 |

The 24-probe cells use `canary-24-v1`, the panel the control arm and EXP-D
use, so the mock calibration at that size is on the exact digest the paper
reports elsewhere; the 8 and 64 cells use synthetic panels because the
mock's behaviour does not depend on probe content. Full profile: 4,274,880
observation nodes and 8,020 verdicts.

Why these numbers. 200 replications give a two-sided 95 percent
Clopper-Pearson interval of [0.024, 0.090] around an observed 0.05, and the
one-sided test of H-A1 has power 0.86 against a true rate of 0.10 and 0.99
against 0.15 before the Holm adjustment (0.84 against 0.12 at the first
Holm step). Pooled over the twelve A1 cells, 2400 replications put an
interval of about [0.042, 0.060] around 0.05. The horizon of 28 in A2 is
the EXP-D horizon (decisions D24 to D26). N = 40 extends the PLAN.md grid
to the largest N that EXP-B uses, so every power estimate in EXP-B has a
calibration estimate at the same N and panel size.

### 3.6 Seeds

Master seed 20261028 is the `MockProvider` seed in every cell. The
analysis seed is 0 in every verdict (the permutation stream is committed to
the verdict and recomputable). The window salt of 3.2 is the only
per-replication seed. `seed.json` records the master seed, the analysis
seed, the salt formula, and the realised seed range of every cell.

## 4. Procedure

1. The smoke profile runs every cell at its smoke replication count from a
   clean tree at the tagged pre-registration commit, writes a run directory
   with `profile: smoke`, and is registered with that profile; it is an
   instrumentation check and is never evidence. It reports the measured
   seconds per observation node and per verdict for each cell.
2. If the smoke timing implies a full-profile wall-clock above 24 CPU-hours
   single-threaded, the replication counts are reduced by a new dated
   protocol version committed before the full run, never after it; the
   logbook records the reason and the old version stays in place.
3. The full profile runs every cell from a clean tree at the commit the
   registry records. Each cell writes one SQLite pollard store under
   `runs/<run_id>/stores/<part>-p<panel>-n<N>.sqlite`; each replication is
   one monitor whose windows are named `<part>-r<replication>-w<index>`;
   current windows are analysed in index order, so A2 produces 28 chained
   verdicts per replication.
4. Every verdict is recomputed from the stored observations with
   `analyze` before the cell summary is written; a mismatch fails the run.
5. The run directory holds `protocol.frozen.json`, `manifest.json`,
   `environment.json`, `seed.json`, and one summary per cell; the stores are
   archived as a zip whose SHA-256 is recorded in the registry and are
   never committed.
6. `epicormic_lab.analysis` writes `analysis/generated/exp_a_<run_id>.json`
   from the cell summaries, and the logbook result entry and the raw finding
   cite the run id. The paper reads only the generated summary.

Cells are independent and run in parallel processes; the order within a
process is A3, A1 by increasing panel size then N, A2. A crash resumes at
the cell boundary; a partially written cell is rerun from its first
replication because pollard's hybrid mode would otherwise serve the
existing observations and the timing record would be wrong (the verdicts
themselves would be unchanged, being pure functions of the observations).

## 5. Statistical analysis plan

Per A1 cell: counts of `drift`, `warning`, `unknown`, `stable`; the drift
rate with its two-sided 95 percent Clopper-Pearson interval; the raw
one-sided exact binomial p-value against p0 = 0.05 and its Holm adjustment
across the twelve cells; the `rule_fired` breakdown; per scorer the ECDF
values and KS distance of S-A1. Across A1: the pooled drift rate and
interval. A2: per scorer and for the union, the count of replications with
an e-process alarm within 28 windows and its interval and one-sided
p-value; the first-alarm window histogram; the same for CUSUM and
Page-Hinkley; the state-level any-drift rate with the breakdown. A3: the
count of `unknown` verdicts. Every rate carries its interval; no rate is
reported without its denominator.

Holm is applied across the twelve A1 cells for H-A1 because twelve
cell-level tests at 0.05 would falsify a calibrated detector in some cell
about 42 percent of the time. H-A2 is one cell and one test. The secondary
quantities are estimates with intervals, not tests.

## 6. Expected results, stated before the run

The permutation test is exact under exchangeability up to Monte Carlo error
and discreteness, and Holm controls the family-wise error across scorers,
so the drift rate in A1 is expected at or below 0.05 and below it where the
scorers are strongly correlated (on the mock, `exact_match` equals
`normalized_match` and `output_tokens` is a function of `output_chars`);
S-A1 should show raw p-values close to uniform for the indicator and
scalar scorers at N 10 and above and visibly conservative at N 5. In A2 the
e-process is expected to alarm on fewer than 5 percent of replications; the
CUSUM and Page-Hinkley rates at the shipped defaults are unknown and are the
reason S-A2 exists. A3 is expected to be 20 of 20 `unknown`.

## 7. What a result does and does not establish

- The mock arm establishes the operating characteristics of the statistics
  under an exchangeable null. It says nothing about any real provider; the
  control arm (section 9) covers the pinned system, and EXP-D covers hosted
  providers.
- A pass of H-A1 is a bound, not an equality: a rate far below alpha is a
  loss of power that EXP-B will show, and it is reported as such.
- The e-process guarantee in epicormic 0.1.0 uses a plug-in baseline rate.
  H-A2 tests the detector as shipped at the EXP-D baseline size; a
  falsification is a statement that this baseline size is too small for
  the anytime-valid claim, and the paper then states the size that would be
  needed, with the two-sample sequential test named as the v0.2 item.
- The 28 verdicts of an A2 replication share one baseline window and are
  dependent; the e-process is one stream and Ville's inequality applies to
  it as a whole, and the CUSUM and Page-Hinkley rates are reported as
  rates of a dependent sequence, which is how EXP-D will use them.
- Latency is excluded from the scorer set by pre-registration (3.4); the
  paper says so wherever the scorer set is described.

## 8. Deviations

Anything this document does not cover is decided before it happens,
written in the logbook with its reason, and applied by a new dated
protocol version when it changes the protocol. Nothing is changed after a
full run starts; a full run that must change is a failed run with a
logbook entry, and the next run is a new run id.

## 9. Control arm

Protocol file `protocol.control.json`, version dated on the day it is
frozen, with its own digest and logbook plan entry. Everything below is
fixed now; only the replication counts wait on the throughput measurement
of `HANDOFF.md` section 6.2.

- Provider: llama-server from llama.cpp release `b9630` serving the GGUF
  with SHA-256
  `60e05f2100071479f596b964f89f510f057ce397ea22f2833a0cfe029bfc2463`, flags
  as in `HANDOFF.md` 6.1, through pollard's OpenAI chat adapter against the
  `/v1` endpoint. The build and model are pinned in `protocol.control.json`
  by their digests and `llama-server --version` output; the GPU, driver,
  and host are recorded in `environment.json`.
- Panel: `canary-24-v1`. Sampling as the panel states: temperature 0.7,
  200 output tokens, `seed` per attempt with the window salt of 3.2 added
  in the step callable; the step callable supplies the model name to the
  adapter and the `ReplayContract` records it.
- Analysis configuration: identical to the mock arm (3.4). `latency_s` is
  excluded for the same reason stated there and is reported descriptively
  per window instead, so that thermal or clock effects are visible without
  entering the verdict.
- Design: part A1 only, panel 24, N in priority order 10, 5, 20, one
  baseline and one current window per replication, the two windows run
  back to back, replications run consecutively so that any slow change in
  the host appears as a between-window effect rather than being averaged
  away.
- Sizing rule, pre-registered: let t be the measured mean seconds per
  completion (HANDOFF 6.2) and B = 24 the GPU-hours allotted to this arm.
  R_10 = min(200, floor(12 h x 3600 / (480 t))), R_5 = min(200, floor(6 h x
  3600 / (240 t))), R_20 = min(100, floor(6 h x 3600 / (960 t))). A cell
  with R below 40 is not run and is reported as not run, because the
  one-sided binomial test cannot detect a rate below 0.20 with fewer than 40
  replications. At t = 1.5 s this gives R_10 = 60, R_5 = 60, and drops
  N = 20. B may be raised by Mike before freezing; it is never changed
  after.
- Hypothesis H-A4: in each control cell the drift probability is at most
  alpha; exact one-sided binomial test at level 0.05 per cell (at R = 60,
  7 or more drift verdicts of 60 falsify; power 0.82 against 0.15), Holm
  across the control cells that run. By decision D11, a falsification is a
  defect in epicormic or in the control setup, not a finding about the
  model; it is reported in the logbook, blocks the control's use in EXP-D
  until explained, and the explanation is itself logged.
- Reporting: as section 5, plus per window the mean and standard deviation
  of `latency_s`, the server's reported prompt and generation tokens per
  second, and the NVML energy per window when the counter is available.

## 10. Roles

Mock arm: run by Mike (HANDOFF section 1), on CPU, with the smoke profile
first. Control arm: run by Mike on the control machine. Runner and analysis
code, the freeze and snapshot scripts, the logbook entries and the tags:
Muntaser. No run of either arm starts before the corresponding protocol is
frozen and tagged.
