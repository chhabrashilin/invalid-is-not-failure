# Phase 0 Report

Date: 2026-08-29. Scope: **infrastructure validation only.**

> **No scientific result is reported here.** No prediction accuracy, no recovery
> heterogeneity, no compute savings, no scheduling gains. The model is a
> deterministic mock. Stage 3 thresholds and hypotheses are unchanged.

---

## Environment

| Component | Value |
|---|---|
| OS | Windows 11 (10.0.26200) |
| CPU | Intel i7-1355U, 10 cores / 12 threads |
| RAM (host) | 15.7 GB total |
| Docker VM | 12 CPUs, 7.58 GB memory, engine 29.5.2, Linux/x86_64 |
| Disk free | 686 GB |
| GPU | Intel UHD integrated only — **no CUDA**. Plan B confirmed as the route |
| uv | 0.11.19 |
| WSL2 | Ubuntu present; `docker-desktop` distro running |

## Repository state

The repository had **no commits** at the start of Phase 0 (carried since Stage 1).
Fixed before any code was written:

- `aa9ce83` — *Archive research design through Stage 3*, on `master`. Preserves
  the abandoned ReSched direction as research provenance, as instructed.
- Working branch `phase0-infrastructure` created from that commit.

## Python setup (P0.1 ✓)

`uv python pin 3.12` → CPython **3.12.13**; `uv sync --group dev`.
`pyproject.toml` + `uv.lock` are the reproducible record. Both mini-swe-agent
(2.4.6) and swebench (5.0.2) declare `requires-python >=3.10`, so 3.12 is
compatible; this was checked against PyPI metadata rather than guessed.
Installed: pydantic 2.13.5, pyyaml 6.0.3, docker 7.2.0, pytest 9.1.1.
**No torch/CUDA** — swebench's base dependency set excludes it and the
`inference` extra was not installed.

## Docker / WSL status (P0.2 ✓)

Daemon was not running at inspection; started via Docker Desktop and verified
with `hello-world`. Instance image
`swebench/sweb.eval.x86_64.astropy_1776_astropy-12907:latest` pulled
successfully — **4.16 GB**, digest `sha256:e082963099ed7d5a5…`.

## Selected benchmark instance

**`astropy__astropy-12907`**, chosen by a rule fixed and written down *before*
execution (`scripts/phase0/select_instance.py`):

> Sort all 500 SWE-bench_Verified `instance_id` values as ASCII strings
> ascending; take the first.

The rule depends only on instance naming — not difficulty, image size, or any
expectation of success — so it cannot be tuned to obtain a pass. Provenance in
`configs/phase0/selected_instance.json` (500 instances enumerated).

## Mock trajectory result (P0.4 ✓)

The synthetic fixture (`tests/conftest.py`) encodes
inspect → edit → test(fail) → edit → test(pass) and drives 48 unit tests
covering serialization, ordering, cumulative accounting, repeat detection, error
categorisation, prefix extraction and leakage. All pass.

## Real agent smoke test (P0.3 ✓)

Run `phase0-smoke-002`, parent session `parent-38504259`: container started from
the real instance image, 6 instrumented steps executed to termination inside
`/testbed`.

## Trajectory logging verification (P0.4 ✓)

Each session writes `session.json`, `steps.jsonl`, `outcome.json`,
`evaluation.json`, `manifest.json`. Parent totals (RESOURCE UNITS = tokens; no
GPU-hour conversion, since there is no GPU to measure):

| Quantity | Value |
|---|---|
| steps / model calls | 6 / 6 |
| tool calls | 6 |
| failed tool calls | 0 |
| prompt tokens (estimated) | 3,304 |
| completion tokens (estimated) | 275 |
| cost | $0.00 |

Feature extraction on the real prefix at k=3 produced all 21 Class-A features
(e.g. `a_budget_fraction_consumed = 0.25` — computed against the pre-declared
cap of 12, not the realized length of 6).

## Evaluator verification (P0.5 ✓ — after a real bug was found and fixed)

**Run 001 failed this criterion.** The evaluator ran but returned
`success=false, tests_passed=null` because pytest reported *"no tests ran"*
(exit 4): the FAIL_TO_PASS node ids
`test_separable[compound_model6-result6]` / `[compound_model9-result9]` are
parametrisations that **only exist after the instance's `test_patch` is
applied**. The harness had skipped that step, so the verdict was meaningless.

Fixed in `apply_test_patch()`: reset the test files to `base_commit`
(`d16bfe05…`) so the agent cannot edit the tests it is judged by, then
`git apply` the instance `test_patch`, then run.

Run 002 result — the evaluator now **discriminates correctly**:

| Session | Fix applied? | Evaluator verdict |
|---|---|---|
| `parent-38504259` | yes | **2 passed, 0 failed → success=True, score 1.00** |
| `cont-same_seed_a` | no | 2 failed → success=False |
| `cont-same_seed_b` | no | 2 failed → success=False |
| `cont-diff_seed_c` | no | 2 failed → success=False |

The evaluator is independent of the trajectory logger and writes its own hashed
raw artifact, so labelling is not circular.

## Checkpoint result (P0.6 ✓)

`docker commit` at the pre-declared step 3 → `phase0/ckpt:604506bbb4b6` (4.17 GB).
`artifacts/phase0/phase0-smoke-002/snapshot.json` records `snapshot_id`,
`parent_session_id`, `checkpoint_step`, container id, image ref and id,
filesystem digest, message-history hash, and cumulative counters.

## Restore result (P0.7 ✓)

Three continuations started from the checkpoint image, each with a **new
session identity** and `parent_session_id` / `forked_at_step` set. The parent's
raw directory was never reopened.

## Same-condition fork result (P0.8, P0.9 ✓)

Three continuations × 3 steps each.

| Comparison | Result |
|---|---|
| same seed (a vs b) | **identical** — no divergence, `first_divergent_index = None` |
| different seed (a vs c) | **divergent at index 0**, detected and recorded |
| outcomes | all three `success=False` |

**n = 3. Nothing scientific is claimed.** Two things are established: forking is
operationally possible, and the divergence-measurement path works in both
directions (it detects identity and it detects difference). Note that fork c
diverged in *actions* while matching in *outcome* — action divergence does not
imply outcome divergence, which matters for how divergence is measured later.

**Critical limitation:** with a mock LM there is *no provider nondeterminism*.
The dominant real source of fork divergence — reported by *The Replay Gap*
(arXiv:2608.08239) as 6–35% for same-model control forks — is **not exercised
here and remains unmeasured.** That measurement is Phase 1 work and is the input
to falsification criterion K6.

## Resource-accounting result (P0.11 ✓)

Cumulative counters for model calls, prompt/completion tokens, tool calls and
failed tool calls are maintained in one place (`TrajectoryRecorder`) and unit
tests assert monotonicity and agreement with manual sums. Units are tokens and
call counts. **No GPU-hour equivalence is fabricated.**

## Oracle-leakage tests (P0.10 ✓)

Nine dedicated tests in `tests/test_oracle_leakage.py`, all passing:

- online-safe models declare no field from the `ORACLE_FIELD_NAMES` registry;
- `extra="forbid"` blocks smuggling an oracle field through a dict;
- `TrajectoryPrefix.step(i)` raises `PrefixBoundaryError` for `i >= k` and `i < 0`;
- a prefix physically retains only the first k steps (future steps absent from memory);
- **the mandatory adversarial test**: five future steps stuffed with obviously
  predictive junk (`tests_passed=10⁴`, `command_head="THE_ANSWER_IS_SUCCESS"`)
  are appended, and prefix features are **bit-identical** to baseline;
- `extract_online_features` raises `TypeError` on a `SessionOutcome` or a raw
  step list — an explicit guard, not incidental duck-typing failure;
- `load_prefix` is monkeypatch-verified never to open `outcome.json` or
  `evaluation.json`;
- `SessionOutcome` and `SessionMeta` share exactly one field (`session_id`).

## Raw-data integrity (P0.11 ✓)

All artifacts hashed into `manifest.json` and made read-only after close.
Independent re-verification of all **8** run directories across both runs:

```
phase0-smoke-001/{parent,cont-same_seed_a,cont-same_seed_b,cont-diff_seed_c}  ok=True
phase0-smoke-002/{parent,cont-same_seed_a,cont-same_seed_b,cont-diff_seed_c}  ok=True
```

The parent manifest was re-verified *after* all forking completed and still
matched. A tampering test confirms `verify_manifest` detects modification.
Writers refuse to reuse a non-empty run directory or rewrite `session.json`.
Run 001's flawed data was **retained, not deleted or edited**; run 002 used a new
`run_id`.

## Reproducibility command (P0.12 ✓)

```bash
uv run python scripts/phase0/run_phase0.py --config configs/phase0/smoke.yaml
```

Full command sequence in `docs/phase0_runbook.md`. Every session records git
commit + dirty flag, resolved config values, benchmark/harness version,
container image digest, and timestamps.

## Failures / issues

1. **Evaluator missed the `test_patch` step** (run 001). Found, fixed, re-run.
   This was the single most valuable outcome of Phase 0 — the bug would have
   silently produced 100% "failure" labels across all of Phase 1.
2. **`docker diff` counts non-agent churn.** `b_files_changed_total = 537` at
   k=3, dominated by conda/pytest cache artifacts rather than agent edits.
   Phase 1 must restrict the diff to repository paths or use `git diff --stat`.
3. **Piping destroys exit-status fidelity.** The scripted prefix used
   `... | tail -5`, so the recorded `exit_status` is `tail`'s (0) and the failing
   pytest run registered as a success with `failed_tool_calls = 0`. Real agents
   pipe constantly. Phase 1 must capture the pipeline's true status
   (e.g. `set -o pipefail`) or the failure-rate features will be badly biased.
4. **Agent-run tests are often unparseable.** Because the pre-patch node ids did
   not exist, the step-3 pytest produced no summary, so `test_invocation=False`
   and `tests_failed=None`. This is direct evidence for the Stage 3 §5 warning
   that test-derived progress proxies are high-risk and agent-controlled.
5. **`uv` reports `python`/`python3` as the Windows Store stub**; all commands
   must go through `uv run`.

Items 2–4 are **feature-quality defects, not architecture defects**. They change
how features are computed, not whether the pipeline works.

## Phase 0 cost

**$0.00.** `docs/research_log.md` contained no `PHASE_0_API_BUDGET_USD` line, so
paid API calls were forbidden and none were made. All model responses came from
the deterministic mock (`model_id` prefixed `mock:` in every record so mocked
sessions can never be confused with real trajectories). Non-monetary cost:
~4.2 GB image pull, ~8.4 GB peak local image storage, ~10 min wall-clock.

## Phase 0 decision

# PASS

All twelve criteria are met:

| | Criterion | Status |
|---|---|---|
| P0.1 | Reproducible env via uv | ✓ |
| P0.2 | Docker/WSL runs the benchmark environment | ✓ |
| P0.3 | Task executes start → termination | ✓ |
| P0.4 | Full trajectory logged in Stage 3 schema | ✓ |
| P0.5 | Evaluator independently produces an outcome | ✓ (after fix) |
| P0.6 | Checkpoint created | ✓ |
| P0.7 | Environment restored from checkpoint | ✓ |
| P0.8 | Continuation runs from restored state | ✓ |
| P0.9 | Two same-condition continuations, divergence quantified | ✓ |
| P0.10 | No oracle leakage into prefix features | ✓ |
| P0.11 | Raw data immutable and hash-verified | ✓ |
| P0.12 | Reproducible from documented commands | ✓ |

The architecture is viable and checkpoint/restore is **not** fundamentally
unsupported on this stack. PASS is recorded with the four measurement caveats
above, which are Phase 1 work items rather than Phase 0 failures.

## Blockers before Phase 1

1. **Record `PHASE_0_API_BUDGET_USD` / a Phase 1 budget** in `docs/research_log.md`.
   Nothing paid may run until it exists.
2. **Fix instrumentation defects 2–4** (repo-scoped diff, `pipefail`, robust test
   parsing) — these directly corrupt Model B features.
3. **Measure real provider fork divergence.** Everything about K6 is unmeasured
   until a real LM is in the loop.
4. **Integrate mini-swe-agent proper.** Phase 0 used a minimal loop that mirrors
   its shape; the real scaffold and its litellm/datasets dependencies are not yet
   installed.
5. **Decide the throughput plan.** ~4.2 GB per instance image and ~40 s per
   fork cycle on this laptop will not scale to 300 sessions × forks; budget a
   cloud VM or accept multi-day runs.
6. **Verify RAM headroom.** Docker VM has 7.58 GB; concurrency beyond ~2
   containers is untested.
