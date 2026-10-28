# Handoff: running the epicormic experiments

This file is for the two people running the experiments for the epicormic
paper, Katie (GitHub `B-urge`) and Mike (GitHub `askmikeai`), and for
Muntaser (`jemsbhai`), who owns the repository, the pre-registrations, and
the manuscript. It says what the experiments are, who runs which part, what
exists in the repository today, what to do first, and how results come back.
Read `README.md` first; its nine repository rules apply to everything below
and are not repeated in full here.

The software under study is epicormic 0.1.0 on pollard 1.6.0, exactly as
released on PyPI (`src/epicormic_lab/pins.py`). epicormic detects provider
drift: a hosted model changing behind a fixed model name. It samples a pinned
canary panel of probe requests N times per window, records every observation
in a pollard execution tree, tests whether the current window differs from
the baseline window beyond sampling variance, and drives pollard's fail-closed
levers from the verdict. The design is `docs/PLAN.md` in the epicormic
repository (https://github.com/jemsbhai/epicormic); section 16 defines the
experiments and section 17 the limitations. The numbers the paper reports
come from the five experiments below and from nowhere else.

## 1. Who does what

| Person | Resource | Owns |
| --- | --- | --- |
| Katie (`B-urge`) | Cloud accounts, 10 USD total budget | EXP-D hosted arm (the daily canary windows against hosted providers); EXP-B and EXP-C (mock provider, CPU only) |
| Mike (`askmikeai`) | Local NVIDIA GPU machine | The local control of decision D11; EXP-A; EXP-D local silent-change arm; EXP-E |
| Muntaser (`jemsbhai`) | Repository owner | Canary panels, pre-registrations and protocol freezes, the runner code in `src/epicormic_lab`, analysis, figures, manuscript; reviews and merges every pull request |

Two points on the split:

- Katie's 10 USD is the whole hosted budget of epicormic decision D17 (10 USD
  per month across all hosted providers, enforced by a pollard `Budget` on
  every window run). Nothing in EXP-B or EXP-C costs money; they run on a
  laptop CPU or on Colab. If the 10 USD is GPU-hour credit rather than API
  credit, say so before spending any of it, because the allocation changes.
- Mike's GPU is the control in every experiment (README rule 5). A drift
  verdict on the control is a defect in epicormic, not a finding, so the
  control has to be pinned and stable before anything else is run.

## 2. What exists today and what does not

Exists at the current commit:

- The repository rules, layout, run lifecycle, and CI (`README.md`,
  `.github/workflows/ci.yml`).
- `src/epicormic_lab/pins.py`: the verified release identities of epicormic
  0.1.0 and pollard 1.6.0, checked by the test suite against what is
  installed.
- `tools/scan_vocabulary.py` and `tools/banned_words.txt`: the vocabulary and
  typography scan that CI runs on every Markdown, Python, notebook, and TeX
  file, including the logbook entries you will write.
- `LOGBOOK.md`, `findings.md`, and `experiments/run_registry.yaml`, all empty
  and waiting for the first entries.
- `.env.example`: the environment variables the hosted arm and the control
  read.

Does not exist yet, and is Muntaser's to write:

- The pre-registrations (`experiments/<exp>/PREREGISTRATION.md` and
  `protocol.json`) for all five experiments.
- The canary panels under `data/panels/`.
- The runner and analysis code (`src/epicormic_lab/providers.py`,
  `protocol.py`, `runs.py`, `analysis.py`, and `scripts/run_exp_*.py`,
  `scripts/freeze_protocol.py`, `scripts/snapshot_environment.py`).

Until a pre-registration is committed and tagged, no run produces evidence.
What you can do now is set up, pin your hardware and software, measure your
throughput, and run the instrumentation checks in section 4. Those numbers
feed the pre-registrations directly: the replication counts, the sample
counts, and the budget split are sized from what your machines and accounts
can deliver.

## 3. Ground rules for runners

1. Pre-registration before data. A `full` run starts only from the tagged
   pre-registration commit of its experiment, with a clean working tree. The
   `smoke` profile is an instrumentation check and never evidence.
2. `LOGBOOK.md` is append-only. Write the plan entry before a run and the
   result entry after it; a failed run gets an entry like any other; a
   correction is a dated addendum citing the original entry. Never edit an
   earlier entry.
3. Raw observation stores (the pollard stores under
   `experiments/*/runs/*/stores/`) are never committed. Commit the run
   manifest, `environment.json`, `seed.json`, the frozen protocol copy, and
   the registry entry. Archive the store as a zip, record its SHA-256 in the
   registry's `store_digests`, and send the archive link and digest to
   Muntaser.
4. Secrets never enter the repository. Keys live in a local `.env` (ignored
   by git) or in your shell environment. Do not paste keys, account ids, or
   billing screenshots into issues, logbook entries, or commits.
5. Never change the software under study. `epicormic==0.1.0` and
   `pollard==1.6.0` are pinned; do not upgrade, patch, or vendor either. If a
   pinned release misbehaves, that is a finding about the release and goes in
   the logbook.
6. Never change a protocol, a panel, or a seed mid-run. A protocol changes
   only by a new, dated version next to the old one, written by Muntaser.
7. The vocabulary scan applies to everything you write here, including
   logbook prose: no em-dashes, no en-dashes, no curly quotes, and none of
   the words in `tools/banned_words.txt`. Run `python tools/scan_vocabulary.py`
   before every push; CI fails otherwise.
8. Work on a branch and open a pull request for anything that changes a
   file: `run/exp-a-full-001`, `logbook/exp-d-window-07`, and so on.
   Muntaser merges. Commit messages follow the repository convention:
   `docs(logbook): EXP-X planned`, `docs(logbook): EXP-X completed`,
   `docs(logbook): EXP-X failed`, `run: EXP-X <run id>`.
9. Report in GitHub issues on this repository, one issue per experiment arm
   you own (`EXP-A`, `EXP-D hosted`, `EXP-D local`, and so on). Put
   throughput numbers, hardware details, blockers, and questions there, so
   the record is in one place.

## 4. First steps for everyone

### 4.1 Install

Windows PowerShell (3.10 or newer; 3.12 is what the owner runs):

```powershell
git clone https://github.com/jemsbhai/epicormic-paper.git
Set-Location epicormic-paper
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Linux and macOS:

```bash
git clone https://github.com/jemsbhai/epicormic-paper.git
cd epicormic-paper
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Then the role extras. Mike: `python -m pip install -e ".[dev,control,energy]"`.
Katie: `python -m pip install -e ".[dev,hosted,notebooks]"`.

### 4.2 The four checks

```
python -m pytest --cov=epicormic_lab --cov-report=term-missing
python -m ruff check src tests scripts tools
python -m mypy src
python tools/scan_vocabulary.py
```

All four must pass on a fresh clone. `tests/test_pins.py` fails if the
installed epicormic or pollard is not the pinned release; that is the
intended behaviour, fix the environment, not the test.

### 4.3 Instrumentation check: the locked mock run

epicormic ships a seeded mock provider, and its README locks the output of a
fixed synthetic run across platforms: the panel digest is the same
everywhere, and the verdict node ids are the same wherever epicormic 0.1.0
runs on pollard 1.6, because every record is content-addressed. Run this
from the activated environment:

```python
from pollard import MemoryStore

from epicormic import AnalysisConfig, Drift, MockProvider, Monitor, Panel, Probe, analyze, observe

panel = Panel(
    name="demo",
    probes=tuple(Probe(f"q{i}", {"model": "demo", "input": f"question {i}"}) for i in range(8)),
    sampling={"temperature": "0.7"},
    seed_from_attempt=True,
)
print("panel", panel.digest)

store = MemoryStore()
observe(panel, window_id="week-1", samples=10, fn=MockProvider(seed=1), store=store)
observe(panel, window_id="week-2", samples=10, fn=MockProvider(seed=2), store=store)
drifted = MockProvider(seed=3, drift=Drift(match_rate=0.4))
observe(panel, window_id="week-3", samples=10, fn=drifted, store=store)

config = AnalysisConfig(scorers=("normalized_match", "output_chars"), permutations=2000)
monitor = Monitor("weekly", panel.digest, ("week-1",), config)
for window_id in ("week-2", "week-3"):
    verdict = analyze(store, monitor, window_id)
    pooled = verdict.payload["scorers"]["normalized_match"]["pooled"]
    print(window_id, verdict.state, "T", pooled["T"], "p_holm", pooled["p_holm"], "node", verdict.node_id[:16])
```

Expected output, byte for byte:

```
panel 5cd5533a081de63dfa77c821f26b12ed56e8f842caed287304a6ad9718d3666c
week-2 stable T -0.0375 p_holm 0.675662 node 4aac2d7f0eed1482
week-3 drift T -0.5375 p_holm 0.0009995 node 291011f05749f1c3
```

Week 2 is a second provider instance with no injected change, and sampling
variance alone does not trip the test. Week 3 matches the baseline forty
percent of the time, and the stratified permutation test rejects. If your
output differs in any character, stop and report it in your issue with your
OS, Python version, and the output of `python -m pip show epicormic pollard`;
do not proceed to real runs on that environment.

The same loop from a shell exercises the command line that the runners will
drive (`docs/cli.md` in the epicormic repository documents every command;
exit codes are the states: 0 stable, 2 warning, 3 drift, 4 unknown, 1
error). In an empty directory, write the panel file and an analysis
configuration first:

```python
from epicormic import Panel, Probe, save_panel

panel = Panel(
    name="demo",
    probes=tuple(Probe(f"q{i}", {"model": "demo", "input": f"question {i}"}) for i in range(8)),
    sampling={"temperature": "0.7"},
    seed_from_attempt=True,
)
save_panel(panel, "panel.json")
```

`config.json`:

```json
{
  "format": "epicormic/config/v1",
  "scorers": ["normalized_match", "exact_match", "output_chars"],
  "permutations": 2000
}
```

`drifted_provider.py` (a step callable with an injected change, resolved by
import, so run the commands from this directory):

```python
from epicormic.mock import Drift, MockProvider

step = MockProvider(seed=7, drift=Drift(match_rate=0.4))
```

Then:

```
epicormic panel digest panel.json
epicormic observe --panel panel.json --store runs.db --window week-1 --samples 10 --fn epicormic.mock:step
epicormic observe --panel panel.json --store runs.db --window week-2 --samples 10 --fn epicormic.mock:step
epicormic observe --panel panel.json --store runs.db --window week-3 --samples 10 --fn drifted_provider:step
epicormic verdict --store runs.db --monitor weekly --panel panel.json --baseline week-1 --current week-2 --config config.json
epicormic verdict --store runs.db --monitor weekly --panel panel.json --baseline week-1 --current week-3 --config config.json
epicormic status --store runs.db --monitor weekly
epicormic report --store runs.db --monitor weekly --out report.json
```

Expected: the digest printed first is the same
`5cd5533a081de63dfa77c821f26b12ed56e8f842caed287304a6ad9718d3666c`; each
observe reports `recorded 80 dispatched 80 ... complete yes`; the week-2
verdict is `stable (no rule fired)` with exit code 0; the week-3 verdict is
`drift (pooled test rejected for normalized_match)` with exit code 3; status
and report exit 3 because the latest state is drift. On Windows, set
`PYTHONPATH` to the current directory if `drifted_provider:step` fails to
import.

The `--config` matters. Without it the default scorer set applies, which
includes `latency_s`, and on the mock provider the microsecond timings shift
systematically between runs, so an A/A pair of mock windows reports
`drift (pooled test rejected for latency_s)`. That is epicormic decision D22
(the e-process and the pooled test have no effect-size floor for latency), it
is documented in the epicormic `docs/cli.md`, and it is why every mock run in
this repository uses a behavioural scorer set. On real providers, latency is
a real operational signal and stays in. `epicormic calibrate` runs an A/A
check in one command (`--windows 2 --prefix aa`); with the config above, every
verdict it prints should be `stable`.

`examples/` in the epicormic repository holds four runnable scripts
(observation, verdicts with recomputation, the levers, and the command line
loop); `python examples/04_cli.py` runs the loop above end to end in a
temporary directory.

### 4.4 Report your environment

Open your issue and record: OS and version, CPU model and core count, RAM,
Python version, the output of `python -m pip show epicormic pollard`, and for
Mike the GPU model, VRAM, driver version, and CUDA version. `environment.json`
will capture the same facts automatically once `scripts/snapshot_environment.py`
exists; until then the issue is the record.

## 5. The experiments

Defined in section 16 of the epicormic `docs/PLAN.md`. The local control is
present in every one of them.

| Id | Question | Providers | Runner |
| --- | --- | --- | --- |
| EXP-A | Calibration: is the false alarm rate of the pooled test within the binomial confidence interval of alpha, and does the e-process alarm on at most alpha of A/A streams? 200 replications per cell at N in {5, 10, 20} | mock, local control | Mike |
| EXP-B | Power: injected drift on the mock by type (match rate, length, latency, tool call swap, refusal rate) and effect size (Cliff's delta in {0.1, 0.2, 0.3, 0.5}) against N in {3, 5, 10, 20, 40} and panel size in {8, 24, 64}; which (N, panel) reaches 0.8 power per type? | mock | Katie |
| EXP-C | Sequential detection delay against false alarm rate for CUSUM, Page-Hinkley, and the e-process on streams with a change point at a known window; calibration of the initial defaults | mock | Katie |
| EXP-D | Longitudinal canary, as re-scoped on 2026-09-30 (epicormic decisions D24 to D26): 28 daily windows on hosted models from the provider families of decision D16, under the 10 USD cap, with a declared snapshot switch on day 15; plus a local silent-change arm in which the served GGUF is swapped under an unchanged model name; the control runs alongside | hosted, local control | Katie (hosted), Mike (local) |
| EXP-E | Cost and energy of monitoring: tokens, USD, wall-clock, and NVML joules per window against the power reached in EXP-B | mock, local control | Mike |

Pre-registered EXP-D hypotheses (PLAN.md section 16): the control stays
`stable`; any `drift` verdict on a hosted model coincides with a
provider-announced change, a fingerprint change, or is reproduced by a second
independent window within one week. The declared switch on day 15 is the
positive control for the fingerprint path: the `ReplayContract` changes and
is acknowledged, so the verdict records `contract_changed: true` and the
migration is told apart from a silent change. The local GGUF swap is the
positive control for the silent path: a real checkpoint change with no
fingerprint change, on hardware we control, so ground truth is known.

## 6. Mike: the local control and the local arms

### 6.1 Stand up the control (decision D11)

The control is the pinned llama.cpp build and model that pollard's EXP-001
used, served through llama-server's OpenAI-compatible endpoint and driven
with per-attempt seeds (`seed_from_attempt`, PLAN.md section 5.2). The
reference values are recorded in `evidence/EXP-001/local-model-result.json`
in the pollard repository (https://github.com/jemsbhai/pollard):

| Item | Reference value |
| --- | --- |
| llama.cpp release | `b9630` (`llama-server --version` printed `version: 9630 (8ed274ef4)`) |
| Reference runtime archive SHA-256 (Windows x86_64 build) | `cbb2a0b1c2459897560a654ed8dd2a816cd3989b81f9e019afd4859964794b7b` |
| Model | Qwen2.5-Coder 7B GGUF, model id `qwen2.5-coder:7b` |
| Model file SHA-256 | `60e05f2100071479f596b964f89f510f057ce397ea22f2833a0cfe029bfc2463` |
| Model file size | 4,683,074,048 bytes |
| Reference GPU | NVIDIA GeForce RTX 4090 Laptop GPU, driver 595.79, energy from `nvmlDeviceGetTotalEnergyConsumption` |

The model digest is the Ollama blob for `qwen2.5-coder:7b`: after
`ollama pull qwen2.5-coder:7b` the file is
`~/.ollama/models/blobs/sha256-60e05f21...` (Linux and macOS) or
`%USERPROFILE%\.ollama\models\blobs\sha256-60e05f21...` (Windows). Any GGUF
whose SHA-256 is exactly that value is the right file; verify with
`sha256sum` or `Get-FileHash -Algorithm SHA256`. If the Ollama tag now
resolves to a different digest, do not substitute another file; report the
digest you got and Muntaser will supply the blob.

For llama.cpp, use release `b9630` for your platform: a prebuilt archive if
one exists for it, otherwise a source build of that tag. Record whichever you
used (archive name and SHA-256, or the build commit) and the output of
`llama-server --version`. The EXP-A pre-registration pins what you actually
have, so if `b9630` cannot be built or run on your machine, report the
nearest release you can run and stop there; do not start runs on an unpinned
build.

Launch with the flags pollard's EXP-001 used, on the port `.env.example`
expects:

```
llama-server -m <path-to-model.gguf> -ngl 99 -c 4096 --host 127.0.0.1 --port 8080 --parallel 1 --no-cache-prompt --cache-ram 0 --no-cache-idle-slots --no-webui
```

Then set `EPICORMIC_LAB_CONTROL_BASE_URL=http://127.0.0.1:8080/v1` in your
`.env` and check the server:

1. `GET /health` returns `{"status":"ok"}`.
2. `GET /props` reports the model alias and `n_ctx` 4096; record both.
3. A chat completion against `/v1/chat/completions` with `"seed": 1` and
   `"temperature": 0.7`, sent twice, returns identical text both times
   (the seed is honoured).
4. The same request with `"seed": 2` returns different text (the seed is
   not ignored).

Steps 3 and 4 are instrumentation checks, not evidence. The control's
stability claim is about distributions across windows, and the experiment
code assigns one seed per attempt from `seed_base`, so a window is a set of
distinct seeds and two windows with different `seed_base` values are
independent draws from one pinned model.

### 6.2 Measure throughput

The control-arm sample counts in EXP-A and EXP-E are sized from your measured
throughput, so this number is needed before the pre-registrations can be
frozen. With the server as above and nothing else on the GPU, report:

- Seconds per completion at `max_tokens` 200 and prompt length about 600
  tokens, averaged over 20 requests, with the standard deviation.
- Prompt and generation tokens per second as reported by llama-server's
  timings.
- Whether `pollard[nvml]` can read the energy counter on your GPU
  (`nvmlDeviceGetTotalEnergyConsumption` is not available on every card or
  driver). EXP-E depends on it; if it is unavailable, say so, and EXP-E is
  re-planned around wall-clock and power sampling instead.

For scale: at the PLAN.md defaults (panel of 24 probes, N = 10) one window is
240 completions. EXP-A at 200 replications per cell is two windows per
replication, so the control arm of EXP-A is of order 10^5 completions across
the three N values, and the pre-registration will cut that to what your
throughput allows within a sensible wall-clock budget, with the cut recorded
before the first run.

### 6.3 Prepare the silent-change arm of EXP-D

The silent arm swaps the served GGUF under an unchanged model name on a
pre-registered day, with no change to the `ReplayContract`, so epicormic sees
a silent change on hardware we control. Before the pre-registration can pin
it, report two or three candidate second files with their SHA-256 digests
and sizes: a different quantization of the same Qwen2.5-Coder 7B checkpoint
and a different Qwen2.5 7B checkpoint at the same quantization are the
natural candidates. Muntaser picks one and records it in the EXP-D
pre-registration. Do not run anything against a candidate yet.

Operationally, the local arm is one window per day for 28 consecutive days
on the same machine, the same build, and the same flags, with only the model
file changing on the pre-registered day. Think about how your machine will
run an unattended daily job (Task Scheduler, cron, or a loop that sleeps),
and whether anything else will share the GPU during those windows; note both
in your issue. pollard's hybrid mode makes a window resumable: rerunning it
serves what exists and dispatches only the missing samples, so a crash
mid-window is recoverable without duplicate observations.

### 6.4 EXP-E

EXP-E measures the cost of monitoring itself: tokens, USD, wall-clock, and
NVML joules per window, against the power reached in EXP-B. It runs on the
same control setup with the energy extra installed. Nothing to do yet beyond
confirming the energy counter in 6.2; the protocol follows EXP-B's results.

## 7. Katie: the hosted arm and the mock experiments

### 7.1 The budget

The hosted budget is 10 USD in total for the 28-day run, which is decision
D17's 10 USD per month. Two layers enforce it:

- In code: every window runs under a pollard `Budget(usd=...)` with the
  `TokenmasterCostMeter` from `epicormic[cost]`, with the per-provider,
  per-window allocation written in the EXP-D pre-registration. A window that
  reaches its allocation records refusal nodes and stops; it never
  overspends.
- At the providers: set a hard monthly spending limit on every account you
  use, at or below its share of the 10 USD, before the first window.

The plan's own arithmetic (PLAN.md section 16): the default panel of 24
probes at N = 10 is 240 calls per model per window, roughly 144K input and
48K output tokens at about 600 plus 200 tokens per call. On a cheap tier
(order of 0.15 and 0.60 USD per million tokens) that is about 0.05 USD per
model-window; on a frontier tier (order of 3 and 15 USD per million) about
1.15 USD. Four cheap-tier models for 28 daily windows is about 5.6 USD, plus
the baseline windows and the second snapshot after the declared switch,
which fits with margin. Frontier tiers do not fit and are out. The
pre-registration pins the exact models, tiers, N, and panel size to the
budget before the first window.

### 7.2 Accounts and keys

Decision D16 names the provider families: OpenAI (Responses API), Anthropic
(Messages), Amazon Bedrock (Converse), and a LiteLLM route (Vertex AI, Azure
AI, or another provider), each through the matching pollard adapter. Report
which of the four you can open an account for and fund from the 10 USD; if
one family is impractical, say so and the pre-registration drops or replaces
it rather than stretching the budget. Keys go in your local `.env` following
`.env.example` (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `AWS_PROFILE` and
`AWS_REGION`, and whatever the LiteLLM route requires). The experiment code
reads them from the process environment only.

Install the hosted extra (`python -m pip install -e ".[dev,hosted]"`) and
confirm that `pollard[openai,anthropic,bedrock,litellm]` imports cleanly on
your machine; report the installed SDK versions, which the pre-registration
pins.

### 7.3 The declared snapshot switch

For each provider that offers dated model snapshots, the pre-registration
names a first snapshot for days 1 to 14 and a second for days 15 to 28. On
day 15 the `ReplayContract` changes (`model_revision`), the change is
acknowledged, and the verdict records `contract_changed: true`. Nothing else
changes on day 15 or on any other day: same panel, same N, same sampling
parameters, same time of day. Report, per provider family, which dated
snapshots are available on the cheap tier now, so the pre-registration can
pick two.

### 7.4 Running the 28 days

- One window per provider per day at the same local time, for 28 consecutive
  days, from one machine that stays available (a laptop that sleeps is a
  risk; a cheap always-on VM or a scheduled job on a machine that is on at
  that hour is safer). Record the UTC time of every window; pollard stamps
  every node with `created_at` as well.
- pollard's hybrid mode makes a window resumable; if a window fails
  partway, rerun it the same day and it dispatches only the missing samples.
- Keep a dated log, in your issue, of every provider announcement during the
  run: model deprecations, snapshot releases, status-page incidents, and
  changelog entries for the four families. The EXP-D hypothesis says any
  drift verdict should coincide with an announced change, a fingerprint
  change, or be reproduced by a second window within a week, so the
  announcement record is part of the evidence.
- A `drift` or `warning` verdict is not an emergency and is not a reason to
  change anything. Note it, keep running, and tell Muntaser; the
  reproduction window is part of the protocol.

### 7.5 EXP-B and EXP-C

Both run on the seeded mock provider only, cost nothing, and need no keys.
EXP-B is a power surface over drift type, effect size, N, and panel size;
EXP-C is detection delay against false alarm rate for the three sequential
detectors on streams with a known change point. Each cell is cheap, but the
grids are large (EXP-B alone is 300 cells before replication, with a
2000-permutation pooled test in every analysis), so wall-clock is CPU-bound
and parallel across cells. Once the runners exist, the `smoke` profile
reports the per-cell time on your machine; report that number and the core
count, and the full-profile replication count is pinned from it. The
notebooks under `notebooks/` are Colab-compatible for these two experiments
if your laptop is the bottleneck.

## 8. How results come back

For every completed run, whether smoke or full, successful or failed:

1. The run directory under `experiments/<exp>/runs/<run_id>/` with
   `protocol.frozen.json`, `manifest.json`, `environment.json`, and
   `seed.json`; the `stores/` directory stays out of git.
2. The registry entry appended to `experiments/run_registry.yaml`, with every
   field in the header of that file filled in, `status` set, and
   `store_digests` holding the SHA-256 of the archived store.
3. The logbook result entry, citing the run id.
4. The archived store (zip) and its digest, sent to Muntaser outside git.
5. A pull request from your branch to `main`, with the four checks passing
   locally and CI green.

Muntaser runs the analysis, regenerates `analysis/generated/` and the
figures, appends the raw finding to `findings.md`, and tags the commit. No
number from a terminal or a notebook goes into the paper; everything is read
from `analysis/generated/`.

## 9. Checklists

Katie:

- [ ] Clone, install `.[dev,hosted,notebooks]`, run the four checks, run the
      locked mock check (4.3), report the environment (4.4) in an issue
      titled `EXP-D hosted`.
- [ ] Report which of the four provider families you can fund from the 10
      USD, and set a hard spending limit on each account.
- [ ] Report the installed SDK versions from the hosted extra.
- [ ] Report the cheap-tier dated snapshots available per family (7.3).
- [ ] Decide and report where the daily job will run for 28 days (7.4).
- [ ] Open a second issue, `EXP-B and EXP-C`, for the mock experiments; the
      per-cell smoke timing goes there once the runners exist.

Mike:

- [ ] Clone, install `.[dev,control,energy]`, run the four checks, run the
      locked mock check (4.3), report the environment (4.4) in an issue
      titled `EXP-A and the control`.
- [ ] Obtain the pinned model file and verify its SHA-256 (6.1).
- [ ] Obtain llama.cpp `b9630` for your platform and record the archive
      digest or build commit and the `--version` output (6.1).
- [ ] Bring up llama-server with the reference flags and complete the four
      server checks (6.1).
- [ ] Report throughput and the NVML energy counter status (6.2).
- [ ] Report candidate second GGUF files for the silent-change arm (6.3) in
      an issue titled `EXP-D local`.
- [ ] Decide and report how the daily local job will run for 28 days (6.3).

Muntaser:

- [ ] Publish decisions D24 to D26 in the epicormic `docs/PLAN.md` so the
      re-scoped EXP-D is on record.
- [ ] Write the canary panels under `data/panels/` and record their digests.
- [ ] Write the runner code and tests in `src/epicormic_lab` and the scripts.
- [ ] Write and tag the pre-registrations, sized from the numbers reported
      above, EXP-A first.

## 10. Questions

Ask in the issue for the arm you are working on. Anything that would change
a protocol, a panel, a budget, or a pin is Muntaser's decision and is
recorded in the logbook or the pre-registration before it takes effect.
