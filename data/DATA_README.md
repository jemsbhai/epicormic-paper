# Data

Provenance of every data file in this directory.

- `panels/`: the pinned canary panels used by the experiments, as plain JSON
  in the epicormic panel format. Each panel's `panel_digest`
  (`epicormic panel digest <file>`) is recorded here and in the
  pre-registration that uses it. Panels are inputs, never outputs: a panel
  changes only by a new file with a new digest.
- `checksums.sha256`: SHA-256 of every data file under `data/` (this
  README excluded), verified before each run and regenerated only when a
  data file is added. Regenerate from this directory with
  `sha256sum panels/*.json > checksums.sha256` (PowerShell:
  `Get-FileHash -Algorithm SHA256 panels\*.json`, lower-cased, in the same
  two-column format).

No raw observation store lives under `data/`; those stay under
`experiments/*/runs/*/stores/`, ignored by git, and are archived by digest
(README rule 4).

| File | Added | Panel digest | Used by |
| --- | --- | --- | --- |
| `panels/canary-24-v1.json` | 2026-10-28 | `8f7883e3ce8f937212a9cd396b1ce318a88e13fa1b8a7369b673a05f10cb3a75` | EXP-A (24-probe cells, control arm), EXP-C, EXP-E |
| `panels/canary-24-v2.json` | 2026-11-09 | `aaba1761326e89fe3f6b27521a55d4b56fb2fee87d05400cdeab88ea0bc18fac` | EXP-D (hosted and local arms) |
| `panels/mock-08-v1.json` | 2026-10-28 | `fe9b9078262c469e0f936a21876309ed38a34d5c7f6466c08db5e32660a2c43c` | EXP-A mock arm, 8-probe cells; EXP-B |
| `panels/mock-64-v1.json` | 2026-10-28 | `c9a567a90e381c57dd0502fa132c11af396d9ccf8ffb0ca696af8905da9946ab` | EXP-A mock arm, 64-probe cells; EXP-B |

Panel digests are `epicormic panel digest <file>` (SHA-256 over the
canonical panel document, domain-separated); file checksums are plain
SHA-256 over the bytes. Both are recorded because a panel file can be
reformatted without changing its digest, and the checksum catches that.

## canary-24-v1

The first canary panel: 24 probes in six families of four, written for the
local control (Qwen2.5-Coder 7B) and for hosted chat models alike. Every
payload is `{"input": "<prompt>"}` only; the model name is supplied by the
step callable and recorded in the window's `ReplayContract`, so one panel
digest serves every provider. Sampling is temperature 0.7 and 200 output
tokens, with one seed per attempt (`seed_from_attempt`, `seed_base` 0,
field `seed`). Prompts constrain the output format ("answer with only the
number", "return only the JSON") so that `normalized_match` and
`exact_match` carry signal at temperature 0.7.

| Family | Probes | Intent | Signals it exercises |
| --- | --- | --- | --- |
| `arithmetic` | `arith-01` to `arith-04` | integer answers with one correct value | match indicators, length |
| `code` | `code-01` to `code-04` | short Python functions, code only | length, tokens, truncation |
| `structured` | `json-01` to `json-04` | JSON-only answers with a fixed shape | match indicators, format drift |
| `instruction` | `instr-01` to `instr-04` | formatting constraints with one correct answer | match indicators |
| `factual` | `fact-01` to `fact-04` | single-token facts | match indicators |
| `boundary` | `bound-01` to `bound-04` | benign safety-information requests that some providers decline | refusal rate, length |

The `boundary` family asks for widely published safety information
(how a pin tumbler lock is picked, which cleaning products must not be
mixed, how phishing and card skimmers work) in one sentence each; it exists
because refusal behaviour is one of the signals most likely to move with a
provider's safety-filter changes. A panel version never changes in place: a
new prompt set is a new file with a new digest.

## canary-24-v2

The hosted variant of `canary-24-v1` for EXP-D: the same 24 probes in the
same order, the same seed settings (`seed_from_attempt`, `seed_base` 0,
field `seed`, `min_samples` 5) and the same 200-token output cap, with the
`temperature` key removed from the sampling block, so every provider
samples at its own default and the request epicormic hands to the step
callable carries no sampling temperature. It was written on 2026-11-09 from
`canary-24-v1` by epicormic 0.2.0's panel API; the probe documents of the
two files are identical, and only `name` and `sampling` differ, which a
test pins.

Why: the temperature pin cannot be held fixed across a declared snapshot
switch on the current cheap tiers. Anthropic's Messages API reference marks
`temperature` deprecated and states that models released after Claude Opus
4.6 (February 5, 2026) reject any value other than 1.0 with a 400 error,
and the Claude Haiku 5.5 migration guide says to omit `temperature`,
`top_p` and `top_k`; Claude Haiku 4.5 (October 15, 2025) still accepts it.
On the OpenAI side, a probe on 2026-11-09 found that
`gpt-5-nano-2025-08-07` rejects `temperature` ("Unsupported parameter")
while `gpt-5.4-nano-2026-03-17` accepts it. A switch whose two snapshots
disagree about a request parameter changes two things at once, so EXP-D
drops the parameter from the panel instead of choosing snapshots around it.
EXP-C's export to EXP-D is tied to the probe set and the geometry (panel 24
at N 10), both of which v2 keeps; the mock arms of EXP-A and EXP-C never
read the temperature (the mock hashes the probe content only) and stay on
v1. Default sampling spreads answers more than temperature 0.7 did, which
lowers baseline agreement and the power of a fixed effect on hosted models;
exchangeability under the null is unaffected. Every pollard node records
the request as sent, so the absence of the parameter is itself recorded.

## mock-08-v1 and mock-64-v1

Synthetic panels for the mock-provider cells of EXP-A and EXP-B: probe ids
`q00` to `q07` and `q00` to `q63`, payload `{"input": "question <i>"}`,
family `mock`, the same sampling and seed settings as `canary-24-v1`. The
mock's behaviour depends on the probe only through a hash of its content,
so these panels vary panel size and nothing else.
