# EXP-C pre-registration: sequential detection delay after a change at a known window

| Field | Value |
| --- | --- |
| Experiment | EXP-C (section 16 of the epicormic `docs/PLAN.md`) |
| Protocol | `protocol.json`, version 2026-10-29, mock arm |
| Protocol digest | `ef5062ae6a7da040e1b4194e79482de6d3d36e61923b12dcda0af7acd5f1124e` |
| Software under study | epicormic 0.2.0 on pollard 1.6.0, pinned in `src/epicormic_lab/pins.py` |
| Panel | `canary-24-v1` `8f7883e3ce8f937212a9cd396b1ce318a88e13fa1b8a7369b673a05f10cb3a75` |
| Pilot | `pilot/pilot-seed7.json` (seed 7, 200 permutations, sizing only, section 3.7) |
| Status | Frozen when this commit is tagged `exp-c-prereg` |

The protocol digest is SHA-256 over the canonical JSON of the protocol file:
keys sorted, separators `,` and `:` with no whitespace, `ensure_ascii`
false, UTF-8. `scripts/freeze_protocol.py` computes exactly this; the run
manifest records it, and a run refuses to start when the file on disk no
longer matches.

## 1. Question

EXP-A asks how often the detectors fire when nothing has changed. EXP-C
asks how soon they fire when something has: the provider changes at a known
window, and the question is the distribution of the delay, in windows,
between the change and the first alarm of each detector, together with the
false alarms each detector produces in the quiet windows before the change.
epicormic 0.2.0 carries four detectors in its verdict: the per-window pooled
permutation test (Layer A), and three sequential detectors on the chain of
windows (Layer B): CUSUM and Page-Hinkley on the per-window pooled statistic
and the betting e-process on the per-observation stream. The state machine
reports `drift` when the pooled test rejects after Holm or when any
sequential detector alarms, so the first `drift` verdict is itself a
detector, and the one EXP-D's hypotheses are written against.

EXP-C runs second in the execution order of decisions D24 to D26 because
its results fix a number EXP-D needs before it opens: the detection-delay
bound after the declared switch on day 15. The geometry of the main part is
therefore EXP-D's geometry exactly: panel 24 at N = 10, one baseline window,
14 quiet windows, a change, and 14 windows after it.

## 2. Hypotheses

Let alpha = 0.05 be the configured level. A chain is one baseline window and
K current windows of one panel at N samples per probe, analysed in order by
one monitor; the null mock answers every window before the change and the
drifted mock answers the change window and every window after it. The
delay of a detector is the index of its first alarm window minus the change
window plus one, so a delay of 1 is an alarm in the first drifted window.
A sticky detector (the e-process, CUSUM, Page-Hinkley) that alarmed before
the change has no delay and is a pre-change false alarm; the pooled test is
window by window, so its delay is its first rejection at or after the
change and any rejection before the change is a pre-change false alarm.

Primary, confirmatory:

- H-C1 (state-level detection at the EXP-D operating point). At panel 24
  and N = 10 with 14 quiet windows, for every drift kind (match, refusal,
  truncation, tool swap, length) at every level in {0.2, 0.3, 0.5}, the
  state machine reports `drift` within 2 windows of the change in at least
  90 percent of chains. Per cell, the count of chains with a state delay of
  at most 2, out of 100, is tested against p0 = 0.90 by the exact one-sided
  binomial test (alternative: below); the fifteen p-values are
  Holm-adjusted at family level 0.05. A cell whose adjusted p-value is at
  or below 0.05 falsifies H-C1 for that cell; at the first Holm step that
  is 80 or fewer detections of 100. The unadjusted flag, 84 or fewer, is
  reported as descriptive. The power of the first-step test is 0.54 against
  a true rate of 0.80 and 0.90 against 0.75; the claim is a floor of 0.90,
  and the estimates with their intervals are what the paper reports.
- H-C2 (quiet-period penalty of the e-process). The e-process is a test of
  the null "the rate has stayed inside the baseline interval since the
  baseline": each bettor's wealth is a nonnegative supermartingale under
  that null, and when the true rate sits strictly inside the interval every
  betting factor has expectation strictly below 1, so the wealth shrinks
  geometrically through every quiet window, and after the change it has to
  climb back from wherever it fell before it can reach the threshold. The
  construction therefore predicts a delay that grows with the number of
  quiet windows before the change, roughly linearly, at a rate set by the
  slowest-decaying fraction of the betting grid on the side of the change. In C3 (match kind, panel 24, N = 10), at each of levels 0.3 and 0.5,
  the delay of the e-process on `normalized_match` with 28 quiet windows is
  stochastically larger than with 0 quiet windows, by at least 3 windows at
  the median. Per level, the 50 delays at 28 quiet windows are tested
  against the 50 at 0 by a one-sided Mann-Whitney U test at level 0.05,
  delays censored at 14 entered as 15 (a tie at the top), Holm across the
  two levels; the median difference is reported with its Hodges-Lehmann
  estimate. A level at which the test does not reject, or at which the
  median difference is below 3 windows, falsifies the claim for that level.

Secondary, reported with intervals and not tested:

- S-C1. The realised effect per scorer: the mean pooled Cliff's delta over
  the post-change windows per cell and scorer, with its standard deviation
  across chains, and the same over the pre-change windows. This is the
  mapping from the nominal level of a drift kind to the effect-size scale
  EXP-B uses.
- S-C2. The delay of every detector and scorer: detection within 1, 2, 7 and
  14 windows with Clopper-Pearson intervals (denominators are the chains
  without a pre-change alarm for that detector), the median and 90th
  percentile delay, the first-alarm window histogram, and the e-process
  half-threshold (`warning`) crossing treated the same way.
- S-C3. Pre-change false alarms over the distinct quiet chains (section
  3.5): per detector and scorer and for the union over scorers, the fraction
  of chains with an alarm before the change. The pooled test's figure is its
  per-window false alarm rate compounded over the quiet windows and is read
  against EXP-A A1 and A2; the e-process figure is read against H-A2.
- S-C4. Window size: C2 against the C1 cells at N = 10, for the match kind
  at levels 0.1 and 0.2, at N in {5, 10, 20}.
- S-C5. Offline recalibration of CUSUM and Page-Hinkley, exploratory. The
  per-window pooled statistic of every chain is in the cell summaries, so
  both detectors can be rerun offline over a grid of parameters without new
  observations: CUSUM over k in {0.05, 0.1, 0.15, 0.2} by h in {0.2, 0.3,
  0.4, 0.6, 0.8, 1.0}, Page-Hinkley over delta in {0.025, 0.05, 0.1} by
  lambda in {0.25, 0.5, 0.75, 1.0}. For each pair: the false alarm rate over
  28 null windows on the EXP-A A2 chains (200) and the C3 quiet chains (50),
  and the mean delay per kind at level 0.2 on the C1 chains. Per detector,
  among the pairs whose A2 false alarm rate has a 95 percent Clopper-Pearson
  upper bound at or below 0.10, the pair with the smallest mean delay at
  level 0.2 averaged over the five kinds is recorded as the recommended
  default for the next epicormic release. This is the calibration section
  16 of the plan asks EXP-C for; it tests nothing, and the chosen values are
  a recommendation, not a finding about 0.2.0.
- S-C6. The e-value at the change: per cell, the median and range of the
  primary scorer's e-value in the last pre-change verdict, which measures
  the wealth lost in the quiet windows and is the quantity behind H-C2.

## 3. Design

### 3.1 Drift kinds and levels

The null provider is `MockProvider(seed=20261029, match_rate=0.9)` with no
drift, as in EXP-A with a new seed. A drift kind is a post-change provider
built by `epicormic_lab.providers.drifted_provider` from the null provider's
specification, a kind name, and a level in (0, 1]:

| Kind | Post-change provider | Primary scorer | Stream |
| --- | --- | --- | --- |
| match | `Drift(match_rate = 0.9 - level)` | `normalized_match` | indicator |
| refusal | `Drift(refusal_rate = level)` | `refusal` | indicator |
| truncation | `Drift(truncation_rate = level)` | `truncated` | indicator |
| tool_swap | mixture: a fraction `level` of requests to `Drift(swap_tool = "search")` | `tool_call_set_jaccard` | sign |
| length | mixture: a fraction `level` of requests to `Drift(length_delta = 20)` | `output_chars` | sign |

The first three drifts are rates in the mock and grade on their own. The
tool swap and the length padding apply to every answer the drifted mock
gives, so a provider that swapped every tool call would realise a Cliff's
delta of 1 at any level; they are graded through a mixture that routes
each request to the drifted mock with probability `level`. The routing is a
hash of the whole request (content and seed), so it is a pure function of
the request, identical in every process and on every rerun, and
independent across the requests of a window. Hashing the seed alone would
not do: the panel gives every probe the seed `seed_base + attempt`, and the
same attempt of every probe would be routed together.

The drifted mock keeps the null's seed. The mock's randomness is a hash of
its seed and the request, so a request whose answer is a variant under the
null is a variant under the drift: the post-change windows are the null
windows with the drift applied on top (common random numbers), which is
what a provider change does to a fixed panel.

Levels: 0.05, 0.1, 0.2, 0.3, 0.5 in C1. The level is the nominal effect; the
realised effect on the primary scorer, measured in the pilot (3.7), is
within 0.01 of it, and S-C1 reports it per cell. The primary scorer is the
one that measures the kind directly; the other scorers move too (a refusal
empties the text, so `normalized_match` and `output_chars` move with
`refusal`; a swapped tool changes the normalized projection, so
`normalized_match` moves with `tool_call_set_jaccard`; a truncated answer
still matches after normalization but not exactly, so `exact_match` moves
with `truncated`), and every scorer is reported. `latency_s` is excluded as in EXP-A section 3.4 (decision D22); no
sleep is injected.

Two kinds feed the e-process through a sign stream rather than an
indicator: `tool_call_set_jaccard` and `output_chars` are scalar scorers,
so the e-process sees the indicator "above the per-probe baseline median",
ties excluded, and its null rate is the baseline's own above-median rate
(D21). On this mock both streams are degenerate, in different ways, and
the pilot (3.7, point 4) measures what that does to the e-process; the
pooled test and the two heuristics work on the scorer values themselves
and are not affected. The indicator-versus-sign contrast is the reason the
five kinds are all run rather than one.

### 3.2 Chains, the change, and the salt

A chain is the baseline window (index 0), `pre_change_windows` quiet
windows answered by the null provider, and `post_change_windows` = 14
windows answered by the drifted provider; the change window is
`pre_change_windows + 1`. The window salt of EXP-A section 3.2 applies
unchanged, `seed_sent = request["seed"] + 100000 * replication + 1000 *
window_index`, inside the step callable, so windows are independent draws
and seeds are disjoint (N at most 20 and at most 43 windows per chain).

The salt depends on the replication and the window index only. Every cell
with the same panel size and N therefore shares its baseline window and its
quiet windows, observation for observation, with every other such cell at
the same replication index: the kinds and levels differ only from the
change window on. This is deliberate. It pairs the comparison of detectors
across kinds and levels by replication, and it means the pre-change false
alarm rates of S-C3 have one denominator per geometry, the distinct quiet
chains, not one per cell (3.5).

### 3.3 Variables

Independent: drift kind and level (C1); samples per probe N in {5, 20}
(C2); the number of quiet windows before the change in {0, 7, 28} (C3,
with 14 from C1).

Dependent, per verdict as in EXP-A: `state`, `rule_fired`, per scorer the
pooled statistic `T`, raw and Holm-adjusted p and the rejection flag; per
scorer the CUSUM and Page-Hinkley statistics and alarm flags, the e-value,
its running maximum, threshold, alarm flag and alarm index, and the
interval behind its null. Derived per chain by
`epicormic_lab.chains.first_alarms`: for each detector and scorer the first
alarm window, whether it preceded the change, and the delay; the first
`drift` verdict and its rule; the first `warning` or `drift`; the realised
effect per scorer; the e-value before the change.

Held constant: the analysis configuration (3.4), the panel, the provider
seed and null match rate, the post-change horizon of 14 windows, the
software pins.

### 3.4 Analysis configuration

Identical to EXP-A version 2026-10-28-r2, section 3.4: epicormic's defaults
with `latency_s` removed from the scorer set; scorers `normalized_match`,
`exact_match`, `tool_call_set_jaccard`, `refusal`, `truncated`,
`output_chars`, `output_tokens`; alpha 0.05, q 0.05, 2000 permutations,
analysis seed 0, `n_min` 5, `effect_min` 0.2, `unknown_fraction` 0.5,
`top_k` 50; CUSUM k = 0.1, h = 0.4; Page-Hinkley delta = 0.05, lambda =
0.5; e-process alpha 0.05 with grid {0.1, 0.25, 0.5, 0.75}. The config
digest is one value across the experiment and is recorded in the manifest.
The detectors are evaluated as shipped; S-C5 is the only place other
parameters appear, offline and labelled exploratory.

### 3.5 Cells and replications

| Part | Panel | N | Quiet windows | Post-change windows | Kinds | Levels | Cells | Replications (full) | Replications (smoke) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 24 | 10 | 14 | 14 | all five | 0.05, 0.1, 0.2, 0.3, 0.5 | 25 | 100 | 2 |
| C2 | 24 | 5, 20 | 14 | 14 | match | 0.1, 0.2 | 4 | 50 | 2 |
| C3 | 24 | 10 | 0, 7, 28 | 14 | match | 0.3, 0.5 | 6 | 50 | 2 |

Cell names: `<part>-p<panel>-n<N>-<kind>-l<level in thousandths>-q<quiet
windows>`, for example `C1-p24-n10-match-l200-q14`. The C3 point at 14
quiet windows is the C1 cell of the same kind and level, whose first 50
replications are the C3 sample at that length; a separate cell would
reproduce the same chains observation for observation. Full profile: 2500
C1 chains of 29 windows, 200 C2 chains of 29, 300 C3 chains of 15, 22 and
43 windows: 83,300 verdicts and about 21.1 million observation nodes.

Why these numbers. The headline quantities are detection fractions within
d windows per cell; 100 chains put a two-sided 95 percent Clopper-Pearson
interval of [0.82, 0.95] around an observed 0.90 and of [0.96, 1] around
100 of 100, and the per-cell test of H-C1 has the power stated in section
2. Fifty chains per C2 and C3 cell estimate a median delay and a detection
fraction with an interval of about plus or minus 0.13 at 0.9; these parts
are comparisons of shapes, not floors. The post-change horizon of 14
windows is EXP-D's: a detector that has not alarmed 14 days after the
declared switch has missed it for EXP-D's purpose, and delays are censored
there. The quiet lengths 0, 7, 14, 28 span EXP-D's geometry and twice it.
N = 5 and N = 20 bracket EXP-D's N = 10 within the EXP-A calibration grid.

Distinct quiet chains, the denominators of S-C3: 100 chains of 14 quiet
windows at panel 24 by N 10, shared by the 25 C1 cells; 50 chains of 28
quiet windows (the C3 cells at that length, whose first 14 windows coincide
with the C1 chains at the same replication index and whose next 14 are new
null windows); 50 chains of 14 at N 5 and 50 at N 20 (C2). The C3 cells
with 7 quiet windows repeat the first 7 windows of the C1 chains and add
no null information; the cells with 0 quiet windows have no pre-change
window and contribute nothing to S-C3.

Disk: a C1 cell is about 700,000 observation nodes, about 1.3 GB of SQLite
at the EXP-A development rate of about 1.9 KB per node, and the full
profile about 40 GB uncompressed. The runner therefore compresses each
cell's store into a zip after the recompute check and removes the
uncompressed store, so that at most a few cells' worth of stores exist at
once; the zip's SHA-256 is in the cell summary and the registry.

### 3.6 Seeds

Master seed 20261029 is the `MockProvider` seed of the null and of every
drifted mock. The analysis seed is 0 in every verdict. The window salt of
3.2 is the only per-replication seed. The mixture routing uses no seed: it
is a hash of the request under the fixed tag `epicormic-lab/mixture/v1:`.
`seed.json` records the master seed, the analysis seed, the salt formula,
the mixture tag, and the realised seed range of every cell.

### 3.7 Pilot, for sizing only

`scripts/pilot_exp_c.py` ran on 2026-10-29 at provider seed 7 (the
experiment uses 20261029), panel 24, N = 10, 14 quiet windows, 14 post-change
windows, 200 permutations instead of 2000 (the sequential detectors do not
depend on the permutation count; the pooled test's p-value resolution does,
and 200 is enough for Holm across seven scorers to reject at 0.05), ten
chains per kind and level over the C1 grid. Its output is committed as
`pilot/pilot-seed7.json`; it sized the design and set the thresholds of
H-C1 and H-C2, and it is not evidence for any claim.

| Kind | Level | Realised delta, primary scorer | First `drift` within 1 / 2 / 14 windows | E-process, primary scorer, within 14 | CUSUM, primary scorer | Page-Hinkley, primary scorer | E-value before the change |
| --- | --- | --- | --- | --- | --- | --- | --- |
| match | 0.05 | -0.056 | 2 / 3 / 6 | 0 of 10 | 0 of 10 | 0 of 10 | 2.7e-08 |
| match | 0.1 | -0.105 | 7 / 8 / 10 | 0 of 10 | 2 of 10, median 13.5 | 0 of 10 | 2.7e-08 |
| match | 0.2 | -0.206 | 10 / 10 / 10 | 8 of 10, median 9 | 10 of 10, median 4 | 10 of 10, median 5 | 2.7e-08 |
| match | 0.3 | -0.307 | 10 / 10 / 10 | 10 of 10, median 6.5 | 10 of 10, median 2 | 10 of 10, median 3 | 2.7e-08 |
| match | 0.5 | -0.509 | 10 / 10 / 10 | 10 of 10, median 3.5 | 10 of 10, median 1 | 10 of 10, median 2 | 2.7e-08 |
| refusal | 0.05 | +0.052 | 9 / 9 / 10 | 0 of 10 | 0 of 10 | 0 of 10 | 0.5 |
| refusal | 0.1 | +0.101 | 10 / 10 / 10 | 0 of 10 | 0 of 10 | 0 of 10 | 0.5 |
| refusal | 0.2 | +0.201 | 10 / 10 / 10 | 10 of 10, median 5 | 10 of 10, median 4 | 10 of 10, median 4.5 | 0.5 |
| refusal | 0.3 | +0.300 | 10 / 10 / 10 | 10 of 10, median 3.5 | 10 of 10, median 2 | 10 of 10, median 3 | 0.5 |
| refusal | 0.5 | +0.498 | 10 / 10 / 10 | 10 of 10, median 2 | 10 of 10, median 2 | 10 of 10, median 2 | 0.5 |
| truncation | 0.05 | +0.051 | 10 / 10 / 10 | 0 of 10 | 0 of 10 | 0 of 10 | 0.5 |
| truncation | 0.1 | +0.100 | 10 / 10 / 10 | 0 of 10 | 0 of 10 | 0 of 10 | 0.5 |
| truncation | 0.2 | +0.198 | 10 / 10 / 10 | 10 of 10, median 6 | 10 of 10, median 5 | 10 of 10, median 5 | 0.5 |
| truncation | 0.3 | +0.298 | 10 / 10 / 10 | 10 of 10, median 4 | 10 of 10, median 2.5 | 10 of 10, median 3 | 0.5 |
| truncation | 0.5 | +0.497 | 10 / 10 / 10 | 10 of 10, median 2 | 10 of 10, median 1 | 10 of 10, median 2 | 0.5 |
| tool_swap | 0.05 | -0.050 | 8 / 10 / 10 | 0 of 10 | 0 of 10 | 0 of 10 | no stream |
| tool_swap | 0.1 | -0.103 | 10 / 10 / 10 | 0 of 10 | 0 of 10 | 0 of 10 | no stream |
| tool_swap | 0.2 | -0.201 | 10 / 10 / 10 | 0 of 10 | 10 of 10, median 4 | 10 of 10, median 5 | no stream |
| tool_swap | 0.3 | -0.301 | 10 / 10 / 10 | 0 of 10 | 10 of 10, median 2 | 10 of 10, median 3 | no stream |
| tool_swap | 0.5 | -0.501 | 10 / 10 / 10 | 0 of 10 | 10 of 10, median 1.5 | 10 of 10, median 2 | no stream |
| length | 0.05 | +0.058 | 1 / 3 / 7 | 0 of 10 | 0 of 10 | 0 of 10 | 0.5 |
| length | 0.1 | +0.110 | 8 / 8 / 10 | 0 of 10 | 2 of 10, median 13 | 1 of 10, median 10 | 0.5 |
| length | 0.2 | +0.208 | 10 / 10 / 10 | 0 of 10 | 10 of 10, median 4.5 | 10 of 10, median 4.5 | 0.5 |
| length | 0.3 | +0.307 | 10 / 10 / 10 | 0 of 10 | 10 of 10, median 2 | 10 of 10, median 3 | 0.5 |
| length | 0.5 | +0.505 | 10 / 10 / 10 | 0 of 10 | 10 of 10, median 1.5 | 10 of 10, median 2 | 0.5 |

Counts are of ten chains; "median" is the median delay in windows over the
chains that alarmed within 14; the e-value is the primary scorer's in the
last quiet verdict. No chain had a pre-change alarm of any detector on any
scorer (ten distinct quiet chains), and every first `drift` verdict in the
pilot came from the pooled test.

What the pilot settled.

1. The realised effect on the primary scorer is within 0.01 of the level
   for every kind and level, so the level is a Cliff's delta to two
   decimals. The other scorers move as section 3.1 says: at level 0.2,
   `normalized_match` moves by about -0.19 under refusal, tool swap and
   length as well as under match, `exact_match` by -0.19 under truncation,
   and `output_chars` by -0.20 under refusal.
2. The state machine reaches `drift` in the first drifted window in every
   chain at level 0.2 and above, for every kind; at level 0.1 in 7 to 10
   of 10 within two windows; at level 0.05 the kinds split, because a
   scorer whose baseline is constant (`refusal`, `truncated`) makes the
   permutation test exact on the few events that land in the current
   window, while `match` and `length` at 0.05 are below the pooled test's
   per-window power at N = 10. The floor of 0.90 within 2 windows in H-C1
   leaves room between the pilot and the claim.
3. The e-process on the detecting side has little wealth left when the
   change comes. For the match kind the e-value of `normalized_match` is
   about 3e-8 (median; 1e-12 to 0.06 across chains) after 14 quiet windows,
   and the downward bettor behind it, the one a drop in the match rate has
   to grow, is many orders of magnitude below that. The delays follow: at
   level 0.5 a median of 3.5 windows, at 0.3 of 6.5, at 0.2 two chains of
   ten miss the 14-window horizon, and at 0.1 and 0.05 all do. A
   pure-Python simulation of the betting formula with the pilot's interval
   (40 streams per setting, 2026-10-29) puts the same streams with no quiet
   windows at a median delay of 1 window at level 0.2 and 0.3, and at 13
   windows with 28 quiet windows at level 0.3. H-C2 and part C3 measure
   that mechanism on the detector as shipped.
4. Two blind spots of the sign-stream reduction on this mock, both
   consequences of the construction and now measured. `tool_call_set_jaccard`
   is constant 1 in the baseline, every value ties the median, and the
   e-process has no stream for it at all ("no stream" in the table); the
   tool swap reaches the e-process only through `normalized_match`, which
   the swapped tool name moves (6 of 10 at level 0.2, 9 at 0.3, 10 at 0.5,
   with the match kind's delays). `output_chars` has a baseline whose
   non-tie values all lie above the per-probe median (the matching answer
   has one length and the variants are longer), so its null rate is 1, the
   upward bettor cannot gain, and padding a fraction of the answers leaves
   every sign at 1: the e-process never alarms on the length kind at any
   level, while the pooled test sees it at once. The constant-zero
   baselines of `refusal` and `truncated` behave differently: the downward
   bettor is frozen at 1 and the upward bettor decays, so the e-value sits
   at 0.5 through the quiet windows and the upward side recovers at a rate
   set by the refusal or truncation rate (median delay 5 and 6 windows at
   level 0.2, 2 at 0.5). These are reported under S-C2 and S-C6 as the
   operating characteristic of the reduction; the paper names them, and a
   different reduction for scalar and constant scorers is a decision for a
   later release.
5. CUSUM and Page-Hinkley at their defaults detect level 0.2 in a median of
   4 to 5 windows for every kind, level 0.3 in 2 to 3, level 0.5 in 1 to 2,
   and level 0.1 late or not at all, which is what k = 0.1 and delta = 0.05
   on a per-window statistic with a standard deviation near 0.06 predict.

## 4. Procedure

1. The smoke profile runs every cell at two replications from a clean tree
   at the tagged pre-registration commit, writes a run directory with
   `profile: smoke`, and is registered with that profile; it is an
   instrumentation check and is never evidence. It reports seconds per
   observation node and per verdict for each cell on the runner's machine.
2. Sizing rule: if the smoke timing projects a full-profile wall-clock above
   12 hours at the runner's worker count, a new dated protocol version
   lowers C1 to 60 and C2 and C3 to 30 replications before the full run,
   never after it; the logbook records the reason and the old version stays
   in place. For orientation, one verdict at panel 24 by N 10 with 2000
   permutations and the recompute check took about 3.9 s on a slow
   two-core machine in the EXP-A development smoke run, which projects
   about 90 CPU-hours for the full profile there.
3. The full profile runs every cell from a clean tree at the commit the
   registry records. Each cell writes one SQLite pollard store under
   `runs/<run_id>/stores/<cell>.sqlite`; each replication is one monitor
   whose windows are named `<part>-r<replication>-w<index>`; current windows
   are analysed in index order by `epicormic_lab.chains`.
4. Every verdict is recomputed from the stored observations with `analyze`
   before the cell summary is written; a mismatch fails the run.
5. The run directory holds `protocol.frozen.json`, `manifest.json`,
   `environment.json`, `seed.json`, and one summary per cell with the
   per-window verdict records of every chain (the pooled statistic per
   scorer per window is what S-C5 reads); each cell's store is zipped after
   its recompute check, its SHA-256 recorded in the summary and the
   registry, the uncompressed store removed, and no store is ever
   committed.
6. The analysis module writes `analysis/generated/exp_c_<run_id>.json` from
   the cell summaries; the logbook result entry and the raw finding cite the
   run id; the paper reads only the generated summary.

Cells are independent and run in parallel processes; the order within a
process is C3, C1 by kind then increasing level, C2. A crash resumes at the
cell boundary; a partially written cell is rerun from its first
replication, for the reason given in EXP-A section 4.

## 5. Statistical analysis plan

Per cell, detector and scorer: the number of chains with a pre-change
alarm; among the rest, the counts with delay at most 1, 2, 7, 14 and their
two-sided 95 percent Clopper-Pearson intervals; the median and 90th
percentile delay when at least half, respectively 90 percent, of those
chains alarmed within 14 windows, and "above 14" otherwise; the first-alarm
window histogram. Per cell: the same for the first `drift` verdict and for
the first `warning` or `drift`, with the `rule_fired` breakdown at the
first `drift`. H-C1: the per-cell exact one-sided binomial p-value and its
Holm adjustment across the 15 cells. H-C2: per level, the Mann-Whitney U
statistic and one-sided p-value for 28 against 0 quiet windows, the
Hodges-Lehmann median difference, and Holm across the two levels; the
median delay at each of the four quiet lengths and the least-squares slope
of the median on the quiet length. S-C1 to S-C6 as stated in section 2.
Every rate carries its interval and its denominator.

Holm is applied across the 15 cells of H-C1 because fifteen cell-level
tests at 0.05 of a true floor would falsify it somewhere about half the
time. H-C2 is two tests. The secondary quantities are estimates with
intervals, not tests.

## 6. Expected results, stated before the run

From the pilot and the construction of the detectors: the state machine
reaches `drift` in the first drifted window through the pooled test at
level 0.2 and above for every kind, within 2 windows at level 0.1 for most
chains, and at level 0.05 at once for the constant-baseline scorers
(`refusal`, `truncated`) and inconsistently for `match` and `length`, where
the per-window power of the pooled test at N = 10 is low. The pooled test
will also show the largest pre-change false alarm fraction, because
fourteen windows at a per-window level near alpha compound (none in the
ten pilot chains, which says little); the e-process will show close to
none; CUSUM and Page-Hinkley at their defaults are unknown under the null
and are the reason S-C3 and S-C5 exist. The e-process at 14 quiet windows
will trail the pooled test by several windows at level 0.3 and 0.5, miss
level 0.2 in part of the chains and level 0.1 in almost all; with 0 quiet
windows it will alarm in the first drifted window at level 0.2 and above;
the delay will grow about linearly in the quiet length (H-C2). The
e-process will never alarm on `tool_call_set_jaccard` (no stream) or on
`output_chars` and `output_tokens` (degenerate sign stream), so for the
tool swap and length kinds its only route is `normalized_match`, and for
the length kind at level 0.2 and below it will mostly miss. CUSUM at k = 0.1
has no expected accumulation on a shift of 0.1, so it will detect level 0.1
late or not at all and level 0.05 not at all, and Page-Hinkley at delta =
0.05 will sit between the two levels.

## 7. What a result does and does not establish

- The mock arm establishes the delay distributions of the statistics under
  a known change on an exchangeable null. It says nothing about any real
  provider; the control arm of EXP-A covers the pinned system, and EXP-D
  covers hosted providers, where the realised effect of a snapshot switch is
  unknown in advance and is the quantity that places EXP-D's observation on
  the C1 grid.
- H-C1 is a floor at the EXP-D operating point, and the export to EXP-D
  is the D90 of the state delay per kind at level 0.2 (section 8). A pass
  does not say the detector is fast on small effects; the level 0.05 and 0.1
  rows say how slow, and EXP-D reports a switch whose realised effect is
  below 0.2 against those rows rather than against the bound.
- H-C2 is a statement about the e-process as a test of the global null,
  which is what its guarantee covers: the false alarm probability over the
  whole monitoring horizon is bounded by alpha, and the price is a delay
  that depends on how long the horizon was quiet. The result does not say
  the e-process is wrong; it measures the operating characteristic that a
  change-detection variant (one e-process per start window under a union
  bound, or an e-detector with restarts) would trade for a different
  guarantee, and that is a decision for a later epicormic release, recorded
  in its plan, not a change made here.
- The two blind spots of 3.7, point 4, are properties of the sign-stream
  reduction on scorers whose baseline is constant or has a point mass at
  the median. The mock makes them total; a real provider makes them
  partial, because answer lengths spread and tool sets vary. EXP-C
  measures them on the mock as shipped; every verdict records the
  baseline's above-median rate and the tie count, so EXP-D's hosted windows
  will show how degenerate the real streams are; and the reduction is a
  candidate for the same later release as the change-detection variant.
- The pooled test's pre-change false alarm fraction over 14 windows is the
  per-window rate compounded, and a per-window detector used daily will
  report `drift` on some quiet day of a four-week run with a probability
  far above alpha. EXP-D's pre-registration must therefore not treat a
  single-day pooled rejection as a finding; its reproduction rule is the
  consequence of S-C3, and S-C3 gives the number it rests on.
- Delays are in windows, and a window is EXP-D's day; nothing here is in
  observations or seconds.
- The CUSUM and Page-Hinkley recommendations of S-C5 are selected on these
  chains and must be evaluated on fresh ones before they are defaults; the
  selection is exploratory and is labelled as such wherever it is quoted.

## 8. Export to EXP-D

EXP-D pre-registers a detection-delay bound for the declared switch on day
15. The bound is the largest D90 of the state delay over the five C1 cells
at level 0.2, in days, read from the EXP-C result entry in the logbook. It
applies to a switch whose realised effect on at least one configured
scorer is 0.2 or more in absolute value, measured on EXP-D's own windows;
a switch below that is outside the bound's domain, and EXP-D reports its
delay against the C1 rows at levels 0.05 and 0.1 instead of against the
bound. If H-C1 is falsified in some cell, the bound is taken over the cells
that pass and the kinds that fail are named in EXP-D's pre-registration.

## 9. Deviations

Anything this document does not cover is decided before it happens,
written in the logbook with its reason, and applied by a new dated
protocol version when it changes the protocol. Nothing is changed after a
full run starts; a full run that must change is a failed run with a
logbook entry, and the next run is a new run id.

## 10. Roles

Mock arm: run by Katie (HANDOFF section 1 and 7.5), on CPU, with the smoke
profile first, from `protocol.json` with its digest, once the runner
exists. Runner and analysis code, the logbook entries and the tags:
Muntaser. No run starts before the protocol is frozen and tagged, and the
runner is tagged `exp-c-frozen` after the registered smoke run.
