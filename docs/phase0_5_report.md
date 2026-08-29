# Phase 0.5 Gemini 2.5 Flash Report

Date: 2026-08-29. Continuation from `c051861`. This section supersedes the
earlier status while preserving every Gemini 3.7 artifact below. No Phase 1A
work was started and no scientific SWE-bench behavior has been observed.

## 1. Research provenance

```text
PHASE_0_5_PRIMARY_MODEL_REJECTED = gemini/gemini-3.7-flash
PHASE_0_5_PRIMARY_REJECTION_REASON = pre-data provider availability gate failure
PHASE_0_5_FALLBACK_MODEL = gemini/gemini-2.5-flash
PHASE_0_5_FALLBACK_CHOSEN_BEFORE_SCIENTIFIC_DATA = true
```

Gemini 3.7 Flash was rejected only because its pre-data gate produced zero
successful probes and six confirmed 503s. Gemini 2.5 Flash was predeclared
before any SWE-bench trajectory or outcome, not selected for benchmark
performance.

Current official Google documentation was retrieved on 2026-08-29 before the
new API call. It identifies model code `gemini-2.5-flash`, lists the stable
release, describes low-latency/high-volume/thinking/agentic uses, lists no
announced shutdown date, and marks Free Tier input and output as free of charge.
Sources are recorded in `artifacts/phase0_5/gemini_2_5_flash_preflight.json`.

LiteLLM 1.98.0 resolved `gemini/gemini-2.5-flash` to
`("gemini-2.5-flash", "gemini")`. The live gate adopted the existing
`GEMINI_API_KEY` name from Windows User scope without logging its value.

## 2. 2.5 availability gate

The fixed prompt `Reply with OK.` was sent; no SWE-bench content was sent.

| metric | result |
|---|---:|
| logical probes attempted / completed | 1 / 1 |
| eventually successful | 0 |
| physical attempts | 1 |
| first-attempt success rate | 0% |
| eventual success rate | 0% |
| 503 count | 0 |
| provider timeout count | 0 |
| 429 count | 0 |
| other error count | 1 (`INVALID_MODEL`) |
| successful latency median / max | N/A / N/A |
| input / output / total tokens | 0 / 0 / 0 |
| actual spend | $0.00 |

The first physical request returned HTTP 404 `NotFoundError` in approximately
547 ms. Per the predeclared no-retry rule for invalid-model errors, the gate
surfaced it immediately and stopped without attempting probes 2–5.

## 3. Gate decision

**STOP.** The API endpoint rejected the officially documented stable model as
not found for this credential/route. The gate therefore cannot satisfy either
the 4/5 eventual-success or 3/5 first-attempt-success requirement. No third
Gemini model was tested.

## 4. Real trajectory

Not run. No mini-SWE-agent trajectory, task behavior, patch, normal termination,
infrastructure rerun, or scientific success/failure sample exists.

## 5. Provider events

One model-specific and global physical attempt was recorded. It ended
`INVALID_MODEL` with HTTP 404. There were no retries, retry delay, 503s,
timeouts, 429s, or recovered failures. The event never entered agent semantics.

## 6. Feature audit

No real-data feature values exist because the gate stopped before the agent.
The infrastructure audit passes: timeout and 503 counts are separate provider
metadata; `PROVIDER_TIMEOUT` and `PROVIDER_UNAVAILABLE` are invalid scientific
terminations; neither may receive `Y_success`; hidden LiteLLM retries are
disabled; and provider records remain outside Model A/Model B `StepRecord`s.

## 7. Independent evaluator

Not run. No valid normal agent termination exists, so no official `test_patch`
or benchmark success label was applied or fabricated.

## 8. Checkpoint / restore

Not run because no valid real parent trajectory exists.

## 9. Same-condition forks

CONTROL A, CONTROL B, and CONTROL C were not run.

## 10. Divergence

No agent action, command sequence, output-token difference, patch hash, outcome
flip, or agent/sampling divergence exists. The only observation is a provider
availability/configuration event: one physical request ending HTTP 404.

## 11. Preliminary K6

**K6_STATUS = UNTESTED.** There are zero valid continuations.

## 12. Resource / token accounting

- historical Gemini 3.7 attempts remain unchanged: 12;
- `GLOBAL_PROVIDER_ATTEMPTS`: 13;
- Gemini-2.5-specific attempts: 1/100 used, 99 remaining;
- Gemini 2.5 input/output/total tokens: 0/0/0;
- real trajectory logical calls and physical attempts: 0/0.

## 13. Actual spend

**$0.00.** No billing, priority inference, paid route, fallback provider, or
third model was enabled.

## 14. Operational profile

The gate ran for approximately 7.84 seconds including process setup; the only
physical request ended after approximately 547 ms. Parent, checkpoint, restore,
fork, evaluator, artifact-size, and disk-growth measurements are N/A because the
real-agent phase did not start.

## 15. Tests

Before the API call, 25 focused tests passed and the full suite reported **116
passed, 1 skipped** (Docker/image unavailable). New coverage includes provider
timeout classification/recovery/exhaustion, unlabeled timeout-invalid runs,
bounded 90-second model requests, and simultaneous global/model ledger updates.
Final suite: **116 passed, 1 skipped** (Docker/image unavailable) in 8.76 s.

## 16. PASS / MODIFY / FAIL

**MODIFY.** The controlled fallback failed its pre-data availability gate on a
non-retryable `INVALID_MODEL` response.

## 17. Blockers before Phase 1A

A research-level model/provider decision is required to resolve the conflict
between current official Google documentation and the live Developer API's HTTP
404 for this free-tier credential/route. The protocol forbids automatically
testing a third Gemini model. All remaining real-trajectory, feature, evaluator,
checkpoint, fork, and K6 requirements remain open.

## 18. Proposed Phase 1A only if PASS

Not proposed because Phase 0.5 is `MODIFY`. Phase 1A remains stopped.

## 19. git diff --stat / status / commit

The work starts from `c0518616d03540cddb901ad9b62cd705e553eca3`. Final diff,
status, and continuation commit are reported after the final test and audit.

---

# Archived Phase 0.5 Availability + Real-Agent Report

Date: 2026-08-29. Continuation from commit `0be22fe`. This section supersedes
the older Phase 0.5 status below while retaining it as provenance. No Phase 1A
work was started and no research hypothesis was changed.

## 1. Availability gate

Exactly `gemini/gemini-3.7-flash` was probed with the fixed prompt `Reply with
OK.`; no SWE-bench content was sent. The global ledger started at the five
physical attempts recorded by `0be22fe` and was not reset.

| metric | result |
|---|---:|
| logical probes attempted | 2 (1 completed; 1 interrupted in flight) |
| probes eventually successful | 0 |
| physical API attempts in this gate | 7 |
| first-attempt success rate | 0% |
| eventual success rate | 0% |
| 503 responses | 6 |
| 429 / 401 / 403 / billing / invalid-model errors | 0 |
| other operational events | 1 in-flight request interrupted |
| median successful latency | N/A (no successful response) |
| maximum successful latency | N/A (no successful response) |
| global ledger | 12/100 used; 88 remain |

Probe 1 exhausted the exact four-attempt policy (initial request, then retries
after 15 s, 30 s, and 60 s) and ended `PROVIDER_UNAVAILABLE`. Probe 2 returned
two further 503s. Its second physical request took approximately 384.5 seconds
to return the second 503; the third request was then interrupted in flight and
is conservatively counted as a physical attempt but not as a 503. The immutable
summary is `artifacts/phase0_5/availability/gate-20260829T154832Z.json`; the
shared ledger is `artifacts/phase0_5/call_ledger.json`.

These observations are an infrastructure gate, not a Gemini capability or
performance benchmark.

## 2. Gate decision

**STOP.** The gate requires at least five successful logical probes and at least
80% eventual success. It observed zero successful probes. Although 88 call slots
remain and no auth/quota/billing error appeared, the availability conditions are
not met.

Per the predeclared rule, SWE-bench was not launched. No model or provider was
substituted.

## 3. Real parent trajectory, if run

Not run because the availability gate stopped. Therefore there is no parent
validity label, no trajectory model-call count, no evaluator outcome, and no
infrastructure rerun. In particular, no benchmark failure label was fabricated.

## 4. Feature audit

No real-data feature audit was possible. The implementation audit is complete:

- provider attempts are written as separate `ProviderCallRecord` objects with
  `provider_attempt_count`, `provider_503_count`,
  `provider_retry_delay_total`, and `provider_final_status`;
- provider records are stored in `provider_calls.jsonl`, outside the semantic
  `StepRecord` stream consumed by Model A/Model B feature extraction;
- only the recovered successful response reaches the agent; a recovered 503
  cannot increment failed-tool counters or behavioral failure features;
- exhaustion raises `PROVIDER_UNAVAILABLE`; its scientific disposition is
  invalid and the schema forbids assigning `Y_success`.

## 5. Checkpoint / restore

Not run because no valid parent trajectory exists. The prior mock checkpoint
evidence is not promoted to real-provider evidence.

## 6. Same-condition forks

CONTROL A and CONTROL B were not run because the gate stopped before the
parent. No valid or invalid fork was created or replaced.

## 7. Agent divergence vs provider events

There were no agent actions and therefore no agent/sampling divergence to
measure. Provider availability events were: seven physical requests, six 503
responses, 150 seconds of declared retry delay across the two attempted logical
probes, and one interrupted in-flight request. None is counted as a trajectory
action or behavioral failure.

## 8. Preliminary K6

**K6_STATUS = UNTESTED.** There are fewer than two valid same-condition
continuations because the availability gate prevented any continuation. Per the
protocol this requires Phase 0.5 to remain `MODIFY`.

## 9. Actual free-tier spend

**$0.00 actual spend.** The same Gemini Developer API free-tier credential and
model were used. No paid priority inference, billing enablement, fallback model,
or substitute provider was used.

## 10. Operational profile

The first logical probe used four physical attempts and 105 seconds of explicit
backoff before `PROVIDER_UNAVAILABLE`. The second used three reserved physical
attempts and 45 seconds of explicit backoff; two completed as 503 and the third
was interrupted while awaiting a response. One completed physical request took
approximately 384.5 seconds before returning 503. This is sufficient to fail the
availability gate, but it is not interpreted as a model performance benchmark.

## 11. Tests

The seven required regressions were added, plus a guard that disables hidden
LiteLLM retries so every physical request is ledgered. Focused provider/adapter
tests pass. The full suite passes with one environment-dependent Docker test
skipped: **113 passed, 1 skipped** (Docker/image unavailable) in 17.26 seconds.

## 12. PASS / MODIFY / FAIL

**MODIFY** — provider availability insufficient for a valid real-agent
checkpoint/fork test at this time.

## 13. Blockers before Phase 1A

1. `gemini/gemini-3.7-flash` must pass the same conservative availability gate.
2. One valid parent trajectory and independent official-patch evaluation must
   complete.
3. A real checkpoint/restore and at least two valid same-condition control
   continuations must complete, allowing a preliminary K6 assessment.

No model/provider change, billing change, fallback, or hypothesis change is
authorized as a workaround.

## 14. Proposed Phase 1A only if PASS

Not proposed: Phase 0.5 is `MODIFY`, not `PASS`. Phase 1A remains stopped.

## 15. git diff --stat / status / commit

The work starts from `0be22fe`. The final diff stat, clean/dirty status, and
continuation commit are reported in the handoff after tests and commit.

---

# Archived Phase 0.5 Report

Date: 2026-08-29. Branch `phase0.5-real-agent-validation` (from `a812835`).

> **UPDATE (continuation from `ae1aefd`, Gemini free tier):** a credential was expected to be
> available for the real-provider steps. It is **not reachable from this process** (see
> §"Gemini free-tier continuation" at the end). Zero model calls were made; the decision
> remains **MODIFY**.

> **No scientific result.** No model trained, no AUROC, no recoverability, no
> scheduler. Stage 3 falsification criteria are unchanged.

---

## Headline

Defects **D1, D2, D3, D4 are fixed and tested**. **D5 and D6 are bounded but not
closed**, and D5 cannot be closed on this machine:

> **There are no LLM API credentials anywhere on this system, and no local
> inference runtime.** No `OPENAI_*`/`ANTHROPIC_*`/`GEMINI_*`/`DEEPSEEK_*`/
> `OPENROUTER_*`/… environment variables, no `~/.config/litellm`, no
> `~/.mini-swe-agent`, no `.env`, no `ollama`/`llama-server`/`lms`/`vllm` binary,
> nothing listening on `localhost:11434`. Steps 9–12 (real agent run, real
> checkpoint, real forks, K6) are therefore **not executable**, independently of
> budget authorisation.

Everything reachable without credentials was done, including running the **real
mini-SWE-agent `DefaultAgent`** end to end under instrumentation.

---

## D1 repository-change fix

`src/instrumentation/repo_state.py`. Replaces `docker diff` (which produced
`files_changed = 537` at step 3 on the real instance, essentially all conda and
pytest-cache churn) with git measurement scoped to the benchmark repository:
`git status --porcelain` + `git diff --numstat <base_commit>`.

Records `files_modified / files_added / files_deleted / lines_added /
lines_deleted`, plus a `measured` flag so a *failed* measurement is never read as
"zero changes". Excludes `.git/`, `__pycache__/`, `.pytest_cache/`, `.tox/`,
`node_modules/`, `*.pyc`, egg-info, and friends.

**Contamination rule enforced twice**: agent-change accounting runs *before* the
evaluator applies `test_patch`, **and** the instance's test files are passed as
`exclude_paths` so the evaluator's own edits can never be attributed to the agent.
Tested by `test_d1_test_patch_can_never_be_attributed_to_the_agent`.

## D2 exit-status fix

`src/checkpoint/docker_env.py`. Every agent command now runs under
`set -o pipefail`. **Verified live in a container, not just asserted:**

| command | `pipefail=True` | `pipefail=False` |
|---|---|---|
| `false \| tail -5` | exit **1** | exit **0** ← the Phase 0 bug |
| `true \| tail -5` | exit 0 | exit 0 |

Without this, the Phase 0 prefix step `pytest … \| tail -5` recorded
`exit_status=0` and `failed_tool_calls=0` for a *failing* test run, biasing every
failure-rate feature toward zero. Timeout keeps its own category (`exit_status
is None` → `timeout`), distinct from `nonzero_exit`.

## D3 test-parser fix

`src/evaluation/test_detect.py`. Structural classification over shell-split argv
(via `shlex`), not substring matching, covering pytest, `python -m pytest`,
unittest, tox, npm/yarn/pnpm, cargo, go, maven, gradle, make. Negative cases are
tested: `grep -r pytest docs/`, `cat test_separable.py`, `git log --grep='go test'`
are correctly **not** test invocations.

Three-valued status, and the middle value is the point:

| status | meaning |
|---|---|
| `TEST_NOT_RUN` | no test command was issued |
| `TEST_RAN_RESULT_PARSED` | ran, counts extracted (includes "no tests ran" → 0/0) |
| `TEST_RAN_RESULT_UNPARSEABLE` | ran, output could not be parsed |

Unparseable output is **never** collapsed into "no test ran". Records
`test_status`, `test_framework`, `test_exit_status`, `tests_passed/failed/errored`.

## mini-SWE-agent integration (D4)

**Installed: mini-swe-agent 2.4.6** (dependency group `agent`; `uv.lock` pins the
tree). Adapter: `src/instrumentation/mini_swe_adapter.py`.

**Not a fork.** Upstream `DefaultAgent.query()` carries the docstring
*"Query the model and return model messages. **Override to add hooks.**"* — the
adapter subclasses `DefaultAgent` and overrides exactly two methods:

| hook | captures |
|---|---|
| `query()` | model latency, token usage, cost, spend-cap enforcement |
| `execute_actions()` | command, exit status, output, repo changes, test outcome |

**Unchanged upstream behaviour:** prompt templates and rendering, action parsing,
`FormatError` handling, the `run()` control flow, message construction, and the
step/cost/wall-time limits (we *tighten* `cost_limit`, never loosen it).

A test asserts the upstream hook docstring still exists, so a silent upstream API
change breaks the build rather than the measurements.

**Mock quarantine:** `SessionMeta.execution_backend` is `mock` |
`mini_swe_agent`; `require_real_backend()` raises `MockBackendRejected` for mock
backends *and* for any `model_id` starting with `mock:`. Phase 1 must call it at
load time.

**Validated without credentials** using upstream's own `DeterministicModel` +
`LocalEnvironment`: the real agent class runs, our `StepRecord`s are produced,
`exit 3` is captured as exit status 3 with a non-`none` error category, and the
spend cap halts the loop.

## Model / provider selection

Researched but **not executed** (no credentials). Prices as advertised on
2026-08-29; `mini-swe-agent` reaches all of these through litellm.

| Model | Provider | $/1M in | $/1M out | Notes |
|---|---|---|---|---|
| Qwen3.7 Flash | Alibaba | 0.03 | 0.13 | cheapest listed |
| GPT-5 nano | OpenAI | 0.05 | — | cheapest OpenAI input |
| DeepSeek V4-Flash | DeepSeek | 0.14 | 0.28 | |
| **Codestral** | **Mistral** | **0.30** | **0.90** | code-specialised |
| MiniMax M3 | MiniMax | 0.30 | 1.20 | 1M context |
| Kimi K2.7 Code | Moonshot | 0.95 | 4.00 | |
| Claude Haiku 4.5 | Anthropic | 1.00 | 5.00 | 200K ctx |
| Claude Sonnet 5 | Anthropic | 2.00 | 10.00 | |

**Proposed Phase 0.5 model: `deepseek/deepseek-v4-flash` or
`mistral/codestral`.** Reasoning: Phase 0.5 needs *enough capability to exercise
the pipeline*, not to solve SWE-bench. Both report token usage through litellm,
are stable, and cost well under a cent per trajectory at 30–75K tokens. A
nano-tier model risks producing malformed actions that exercise `FormatError`
paths rather than the normal path.

**This selection is a recommendation, not a decision.** It should be confirmed
alongside the budget.

## Budget authorization

> **SUPERSEDED** by the Gemini free-tier continuation below. The paid-provider
> recommendation in the previous two sections was the state as of `ae1aefd`; the
> user has since directed a **$0.00 free-tier** run on
> `gemini/gemini-3.7-flash` with a 100-call ceiling. Retained unedited as
> provenance — see "Gemini free-tier continuation" for the authorisation
> actually in force and for why the dollar cap was replaced by a call ceiling.

*(As of `ae1aefd`)* **NOT GRANTED — and correctly so.** `docs/research_log.md`
contained no `PHASE_0_5_API_BUDGET_USD` line, so no paid call was made. I did not
write one: authorising spend is the user's decision, not mine, and there were no
credentials to spend with regardless.

**Recommended cap at the time: `PHASE_0_5_API_BUDGET_USD = 2.00`.** Sized for 1
real trajectory (~75K tokens ≈ $0.02–0.08 at the rates above) + 1 checkpoint +
2–3 continuations, with ~20× headroom.

## Selected SWE-bench instance

Pre-declared deterministic rule, seed committed to the repo
(`scripts/phase0/select_phase05_instances.py`):
`sort by sha256("resched-phase0.5-2026|" + instance_id)`, take first three of 500.

| rank | instance_id | key |
|---|---|---|
| **1 (to run)** | `matplotlib__matplotlib-23412` | `0007ce7baf698dfe` |
| 2 | `django__django-14765` | `00142349ca1f174d` |
| 3 | `astropy__astropy-14096` | `013b778d12252f7b` |

Fall through to #2/#3 **only** on infrastructure failure. A failed task is a
valid outcome and must not trigger a switch.

## Real trajectory / evaluation / checkpoint / control forks / divergence

**NOT EXECUTED — blocked on credentials.** Steps 9, 10, 11 were not performed
with a real model. The machinery for all three is implemented and exercised
against a deterministic model, but no real-agent trajectory, real checkpoint on a
real run, or real control forks exist.

**K6_STATUS = UNTESTED.** Phase 0's forks used a mock LM, which has no provider
nondeterminism; sampling variance under a real model is exactly what K6 concerns.
Reporting anything else would be false.

## Online-feature audit

Cannot be completed against a real trajectory. Partial audit against the Phase 0
real-container run and the fixture:

| feature | source | audit |
|---|---|---|
| `b_failed_tool_calls` | `error_category != none` | correct on fixture (1 failure); **was wrong pre-D2 on piped commands**, now fixed |
| `b_max_command_repeat` | normalized-command counter | correct — `pytest -q` at steps 2 and 4 → repeat count 1 |
| `b_test_invocations` / `b_test_runs_parsed` / `b_test_runs_unparseable` | D3 detector | correct on fixtures; **was 0 pre-D3** on real piped pytest |
| `b_repo_files_changed` | git porcelain | replaces the meaningless 537; not yet audited against a real agent edit |
| `a_budget_fraction_consumed` | pre-declared cap | correct (3/12 = 0.25) |

**Full audit remains outstanding** and is a Phase 1 gate.

## Resource accounting

Unchanged units: tokens, model calls, tool calls, wall-clock (Stage 3 §11). No
GPU-hour conversion is fabricated. Under a real provider, `usage.prompt_tokens` /
`completion_tokens` and upstream's `cost` are used; `estimate_tokens` (~4
chars/token) is the mock-only fallback and its use is visible via the `mock:`
model id.

## Local performance profile (D6)

Measured on this machine against the real 4.16 GB instance image:

| operation | seconds |
|---|---|
| container start | 0.62 |
| trivial `exec` | 0.83 |
| `git status --porcelain` (per step, D1) | 0.97 |
| pytest, 2 tests + conda activate | 6.95 |
| **`docker commit` (checkpoint)** | **68.0** |
| restore (start from committed image) | 0.89 |
| cleanup (2 containers + image) | 1.56 |

Docker currently holds 24.45 GB images + 16.87 GB build cache + 3.69 GB volumes.

**`docker commit` at 68 s is the binding constraint**, and it confirms the Stage 3
warning taken from arXiv:2510.05556 that container commits are "not fast enough";
Shepherd (arXiv:2605.10913) reports overlay checkpoints in the 157–252 ms band.

### Estimated Phase 1 requirements (planning only, not a commitment)

Per session: ~2 s/step local overhead (exec + git status) + model latency, which
dominates. At 30–80 steps and 30–75K tokens, expect **10–25 min wall-clock per
session** and **$0.01–0.10** at the proposed model rates.

| sessions | wall-clock (sequential) | checkpoints (68 s each) | API cost est. |
|---|---|---|---|
| 10 | 2–4 h | 11 min | $0.1–1 |
| 25 | 4–10 h | 28 min | $0.3–2.5 |
| 60 | 10–25 h | 68 min | $0.6–6 |
| 120 | 20–50 h | 2.3 h | $1.2–12 |
| **300** (Stage 3 target) | **50–125 h (2–5 days)** | **5.7 h** | **$3–30** |

Plus Stage 3's ~600 continuations: ~68 s commit is paid once per *state*
(~40 states ≈ 45 min), continuations themselves restore in <1 s.

**Storage is the harder problem.** SWE-bench Verified spans 12 repositories but
images are per-instance at ~2–4 GB. 300 sessions across ~100 distinct instances
implies **~200–400 GB** of images. 687 GB is free, so it fits — but only with
aggressive prune-between-batches, and only if instances are batched by image.

**Conclusion:** local sequential execution is *feasible but slow* (2–5 days
continuous) and disk-hungry. Recommend batching by instance image with pruning,
and treating a cloud VM as an optimisation rather than a necessity. No cloud
infrastructure was provisioned.

## API spend

**$0.00.** No paid call was made. No credentials exist to make one.

## Methodological issues discovered

1. **No credentials / no local runtime** — the blocking discovery. Steps 9–12
   cannot run here at all.
2. **`docker commit` costs 68 s per checkpoint** — tolerable at Stage 3's ~40
   states, prohibitive if checkpoint density rises. Overlay checkpointing
   (Shepherd/Crab) becomes worth adopting before any denser design.
3. **Per-step `git status` adds ~1 s/step.** At 80 steps that is ~80 s per
   session of pure instrumentation overhead. Phase 1 should consider measuring
   repo state every *k* steps, or only after commands that plausibly write.
4. **Renames**: counted once as a modification, not as add+delete. A decision,
   now documented and tested, not an accident.
5. **`_probe`-style upstream inspection matters**: `AgentConfig` requires
   `system_template`/`instance_template`, so a bare `InstrumentedAgent(...)`
   raises. Any Phase 1 runner must supply templates or load a shipped config.

## Decision

# MODIFY

Not PASS: the PASS criteria explicitly require "mini-SWE-agent proper runs
end-to-end", "one valid real trajectory exists", "checkpoint/restore succeeds on
real execution", and "at least two same-condition real forks run". None of the
*real-model* criteria were met, because no credentials exist on this machine.

Not FAIL: nothing discovered suggests the architecture cannot support the design.
Checkpoint/restore works (68 s, measured), the real agent class runs under
instrumentation, the evaluator is correct, and D1–D4 are fixed and tested. The
blockers are procurement and authorisation, not viability.

## Blockers before Phase 1

1. **Provide LLM API credentials** (env var or `.env`), or install a local
   runtime. Nothing in Steps 9–12 can proceed otherwise.
2. **Write `PHASE_0_5_API_BUDGET_USD = <cap>` in `docs/research_log.md`** and
   confirm the model choice. Recommended: `2.00`, DeepSeek V4-Flash or Codestral.
3. **Then re-run Phase 0.5 Steps 9–12** on `matplotlib__matplotlib-23412`:
   real trajectory → feature audit → real checkpoint → ≥2 same-condition forks →
   K6 preliminary status.
4. **Complete the online-feature audit** against that real trajectory.
5. **Decide the repo-measurement cadence** (issue 3) before it costs 80 s/session
   × 300 sessions.
6. **Plan image storage/pruning** for ~200–400 GB across Phase 1.


---

# Gemini free-tier continuation (from `ae1aefd`)

## 1. Verified model identifier

`gemini/gemini-3.7-flash` — the `gemini/` prefix is required; without it litellm routes to
Vertex AI and demands full GCP credentials.

| check | result |
|---|---|
| Model documented on ai.google.dev | **Yes** — "latest and most capable Flash model"; banner "Gemini 3.7 Flash is now available" |
| **Free-tier availability** | **NOT VERIFIABLE FROM DOCS** — the rate-limits page no longer publishes a static free-tier table (it defers to the per-account AI Studio dashboard), and `gemini-3.7-flash` appears in no rate-limit table there. Only Batch API Tier 1–3 tables are shown. **Confirm in your AI Studio dashboard.** |
| LiteLLM env var | **`GEMINI_API_KEY`** (documented) |
| LiteLLM resolution (offline) | `get_llm_provider("gemini/gemini-3.7-flash")` → `("gemini-3.7-flash", "gemini")`, litellm 1.98.0 |
| mini-swe-agent 2.4.6 compatibility | `get_model()` resolves it; the Anthropic-only `set_cache_control` default correctly does not apply |

## 2. API / free-tier connectivity status

**BLOCKED — no credential reachable.** Checked without ever reading a value: process
environment (bash + PowerShell), Windows **User** and **Machine** registry scopes, and
`%LOCALAPPDATA%\mini-swe-agent\mini-swe-agent\.env`, `~/.config/mini-swe-agent/.env`,
`resched/.env`, `research/.env`, `~/.env`. `GEMINI_API_KEY`, `GOOGLE_API_KEY`,
`GOOGLE_GENAI_API_KEY` are absent from **all** of them.

Most likely cause: the variable was set in a different terminal *after* this session's tool
processes started. Env vars do not propagate into already-running processes.

`scripts/phase0/preflight_gemini.py` executed and stopped at check 1 (exit code 2), **zero
model calls made**. No substitute model was used, per the milestone rule.

## 3–5. Trajectory, calls, cost

| quantity | value |
|---|---|
| real trajectory | **not run** |
| model calls | **0** |
| prompt / completion tokens | 0 / 0 |
| rate-limit errors | 0 (none attempted) |
| **monetary cost** | **$0.00** |

## 6–9. Feature audit, evaluator, checkpoint/restore, fork divergence

**All blocked on the credential.** No real-data feature audit, no real checkpoint, no real
forks, no divergence numbers.

## 10. Preliminary K6 status

**`K6_STATUS = UNTESTED`.** Unchanged. Reporting anything else from zero real continuations
would be false.

## 11. Free-tier quota / rate-limit issues

None encountered — no request was attempted. Note the open item: free-tier eligibility for
this specific model could not be confirmed from published documentation.

## Free-tier budget enforcement — a finding that changed the mechanism

**litellm carries a paid-tier price for `gemini/gemini-3.7-flash`**: `input_cost_per_token
= 7.5e-07`, `output_cost_per_token = 3.75e-06` ($0.75 / $3.75 per 1M). So litellm computes a
**non-zero cost even for free-tier calls**, and a literal `cost_limit = 0.00` would either
abort at call #1 or read as "no cap" in our tightening logic.

The $0 authorisation is therefore enforced as a **hard ceiling on model calls**, not dollars:

- `CallBudget` / `CallCapExceeded` in `src/instrumentation/mini_swe_adapter.py`
- one shared ledger passed to the parent run and every fork, so the ceiling spans the milestone
- checked **before** each call inside the `query()` hook
- 3 tests, including one asserting the ledger is shared across sessions and one documenting
  why the dollar cap is unusable here

`PHASE_0_5_MAX_MODEL_CALLS = 100`.

## Data / privacy confirmation

Phase 0.5 sends only the SWE-bench task statement and public repository content from the
official instance image, agent-generated context, and benchmark commands and their output.
It never sends API keys, personal files, unrelated environment contents, credentials, or
private repository data. Safeguards already in the code: commands and outputs are stored as
hashes plus bounded heads; environment variables are never captured; the preflight reads only
the *existence* of the credential; the connectivity probe sends the literal string `"hi"`.

## 12. Decision

# MODIFY

Two blockers, neither of which is a viability problem:

1. **Credential not visible to this process.** Set `GEMINI_API_KEY` and start the harness from
   that shell (or `setx` and restart the session). Never place it in a git-tracked file.
2. **Free-tier eligibility for `gemini-3.7-flash` is undocumented publicly.** Confirm it in
   the AI Studio rate-limit dashboard for this account before the run.

Then `uv run --group agent python scripts/phase0/preflight_gemini.py` gates everything
downstream.


---

# Gemini run attempt 2 (from `ef9cc01`)

**Free-tier documentation objection withdrawn.** The user independently verified that
`gemini-3.7-flash` is GA and free-of-charge (input, output, context caching) on the Gemini
Developer API free tier. Absence of a static RPM/TPM/RPD table is no longer treated as a
blocker.

**The run still could not start: the credential is not present in this process.**

| scope checked (values never read) | result |
|---|---|
| bash / PowerShell process env | absent |
| Windows User + Machine registry scopes | absent |
| `HKCU:\Environment` enumeration | no GEMINI/GOOGLE names at all |
| all six `.env` candidate paths | absent |
| any env name matching KEY/TOKEN/SECRET/CRED/API | only `CLAUDE_CODE_MESSAGING_TOKEN` |
| `.env*` modified in last 24h under user profile | none |

**Model calls: 0. Actual spend: $0.00. Ledger: 0/100.**

**Root cause:** environment variables never propagate into an already-running process. The tool
shells are children of a harness started before the variable was set. `HKCU:\Environment` holds
no such name, so `setx` was not used either — the value most likely exists only in a different
terminal's process tree.

**Fix added — no restart required.** The preflight now loads mini-swe-agent's own global `.env`
(`%LOCALAPPDATA%\mini-swe-agent\mini-swe-agent\.env`) before checking. Writing
`GEMINI_API_KEY=<key>` into that file is read at import time by the child process, which works
where an inherited environment block cannot. The file is outside the repository and cannot be
committed. Two tests pin it to upstream's config dir and assert the preflight never reads the
value.

**Decision: MODIFY.** `K6_STATUS = UNTESTED`.
