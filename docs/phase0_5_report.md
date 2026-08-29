# Phase 0.5 Report

Date: 2026-08-29. Branch `phase0.5-real-agent-validation` (from `a812835`).

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

**NOT GRANTED — and correctly so.** `docs/research_log.md` contains no
`PHASE_0_5_API_BUDGET_USD` line, so no paid call was made. I have not written
one: authorising spend is the user's decision, not mine, and there are no
credentials to spend with regardless.

**Recommended cap: `PHASE_0_5_API_BUDGET_USD = 2.00`.** Sized for 1 real
trajectory (~75K tokens ≈ $0.02–0.08 at the rates above) + 1 checkpoint +
2–3 continuations, with ~20× headroom for retries and a longer-than-expected
trajectory. Two independent mechanisms already enforce it in code
(`InstrumentationContext.spend_cap_usd` pre-call check, and upstream
`config.cost_limit`), so the cap is programmatic, not attentional.

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
