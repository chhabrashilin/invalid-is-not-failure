# Stage 3 — Measurement Design and Signal-Actionability Kill Test

Date: 2026-08-29. **Design only. No data collected, no code written, no paid API calls made.**
Purpose: specify an experiment that could *kill* the success-aware allocation thesis before any
scheduler is built.

Verification levels as in `related_work.md`: V1 = landing page fetched, abstract read verbatim;
V2 = full text read; V3 = index/publisher confirmed; U = search text only.

---

## 1. Research questions

| ID | Question | Kills the thesis if |
|---|---|---|
| **RQ3.1** | How early can eventual task outcome be predicted from **scheduler-observable** trajectory information alone? | Only after most compute is spent |
| **RQ3.2** | How much earlier, if at all, do **model-internal** signals predict outcome? | Only white-box works, and white-box is impractical to serve |
| **RQ3.3** | Is the signal stronger than trivial proxies (session age, tokens consumed, context length, prior failure count)? | It is not |
| **RQ3.4** | Does P(success) meaningfully **change** during a trajectory? | It is essentially fixed at admission — then this is task routing, not scheduling |
| **RQ3.5** | **Does additional compute have heterogeneous marginal value across sessions?** | Recovery curves are homogeneous — no allocation problem exists |

RQ3.5 is the load-bearing question. RQ3.1–3.4 can all succeed and the thesis still dies if
RQ3.5 fails.

### Standing correction to Stage 2C

Stage 2C wrongly framed *Failure as a Process* (2607.09510, V1) and *Doomed from the Start*
(2607.06503, V1) as contradictory. They are not. The first concerns **externally observable**
failure signals arriving late; the second concerns **internal activation** signals arriving
early. Both can hold simultaneously, and if they do, the *conjunction* is the most consequential
possible finding for us: it would mean success-aware scheduling is feasible **only** for
self-hosted open-weight models. This design therefore separates three signal classes throughout.

---

## 2. Operational definitions

### 2.1 Signal classes (never mixed)

| Class | Definition | Available to a deployed scheduler? |
|---|---|---|
| **A — Black-box** | Step index, elapsed wall-clock, prompt/completion tokens, context length, action type, tool name, exit status, error category, repeated-command / repeated-error indicators, test outcomes visible in tool output, action diversity, retry count, latency | **Yes**, for any model including third-party APIs |
| **A′ — Grey-box** | Token logprobs, output entropy, top-k margins — obtainable from *some* hosted APIs without weight access | **Sometimes.** Must be reported separately; availability is provider-dependent |
| **B — White-box** | Hidden activations, layer representations, learned probe outputs | **Only** for self-hosted open-weight models |
| **C — Oracle / post-hoc** | Eventual success, human-annotated decisive error, failure-lock-in timestamp, final trajectory length, anything from the future of the trajectory | **NEVER.** Analysis-only |

**Enforcement (learned from Stage 1 invariant I1).** Class C is excluded *structurally*, not by
discipline: the feature-extraction function receives a `TrajectoryPrefix` object that physically
cannot address events at index > t, and the loader refuses to construct a prefix from a record
containing outcome fields. Any use of C is a bug that fails a test, not a judgement call.

**The normalization trap.** "20% of final trajectory length" is Class C. Checkpoints must be
indexed by **cumulative consumed resource** (tokens generated, model calls, wall-clock), which is
knowable online. Final-length normalization appears in this design **only** in the post-hoc
oracle analysis (M10), clearly labelled.

### 2.2 STRE (internal placeholder only)

```
STRE = successfully completed tasks / total inference resource consumed
```
Units: successful tasks per million generated tokens (API path); successful tasks per GPU-hour
(self-hosted path). **Not claimed as novel.** "Goodput" is unavailable — GoodServe
(2605.16867, V1) already uses it for SLO/latency-attaining throughput.

### 2.3 MCV (internal placeholder only)

```
MCV_i(b, t) = [ P(success | prefix_i(t), + budget b) − P(success | prefix_i(t), + 0) ] / cost(b)
```
**Not claimed as novel.** The conceptual point that matters: *success probability is not
marginal value*. A session at P=0.20 that rises to 0.60 with one more call is worth more compute
than one at P=0.80 that rises to 0.81.

---

## 3. Platform selection

### 3.1 Scoring

10 = best. Scores are judgements from the sources cited in §3.3, not measurements.

| Criterion | mini-SWE-agent + SWE-bench Verified | SWE-agent + SWE-bench Verified | OpenHands + SWE-bench | Harbor/Terminus + Terminal-Bench 2.0 |
|---|---|---|---|---|
| Reproducibility | 9 | 8 | 6 | 9 |
| Automatic success evaluation | 10 | 10 | 10 | 10 |
| Complete trajectory logging | **10** (trajectory ≡ message list) | 8 | 7 (event stream, complex) | 8 |
| Cost | 8 | 6 | 5 | 7 |
| Runtime | 8 | 6 | 4 | 6 |
| Pause / resume / fork | **9** (linear history + container) | 6 | 4 | 7 |
| Runs open-weight models | 9 | 8 | 8 | 8 |
| Runs API models | 10 | 10 | 10 | 10 |
| Task diversity | 7 (12 Python repos) | 7 | 7 | **9** (89 varied terminal tasks) |
| Literature overlap (10 = less crowded) | 4 | 4 | 5 | 6 |
| Ease of step-level instrumentation | **10** (~100 lines) | 6 | 3 | 6 |
| Yields both successes and failures | 8 (tunable via model choice) | 8 | 8 | **9** (harder benchmark) |
| **Total** | **102** | **87** | **77** | **95** |

### 3.2 Selection

- **Primary: mini-SWE-agent + SWE-bench Verified.**
- **Backup: Harbor + Terminal-Bench 2.0** (89 tasks), which also supports mini-SWE-agent, so the
  instrumentation transfers.

### 3.3 Why (not popularity)

1. **The trajectory *is* the message list.** mini-SWE-agent has "a completely linear history —
   every step of the agent just appends to the messages and there's no difference between the
   trajectory and the messages that you pass on to the LM" (project README, V3). This removes
   an entire class of schema ambiguity and makes forking (§7) a matter of truncating a list and
   restoring a container, rather than reconstructing framework-internal state.
2. **Bash-only, no tool-calling interface** — one action type, so "repeated command" and "error
   category" are well-defined rather than framework-specific.
3. **~100 lines** — every instrumentation point is auditable, which matters because Class-C
   leakage is the primary threat to this study's validity.
4. **Deterministic pass/fail oracle.** SWE-bench Verified is 500 human-validated instances from
   twelve Python repositories with hidden test suites, run in sandboxed Docker with pinned
   dependencies and no network (V3).
5. **Outcome balance is a design lever.** mini-SWE-agent reportedly reaches >74% on SWE-bench
   Verified with strong models (project README, V3; a v2 bash-only slice reported at 76.8% in
   April 2026, U). A 74/26 split is poor for prediction statistics. **We deliberately select a
   weaker/cheaper model to target a ~50% pass rate**, which maximizes statistical power and
   reduces cost simultaneously. This is declared *before* data collection precisely so it cannot
   later look like outcome-shopping.
6. Terminal-Bench 2.0 is the backup because its 89 tasks (V3) give better task diversity but too
   few instances for the prediction statistics in §9.

**Rejected:** OpenHands (event-stream complexity, heavy runtime, hardest to fork); SWE-agent
(strictly dominated by mini-SWE-agent for our purpose).

---

## 4. Trajectory schema

One immutable JSONL record per session; one line per step. Raw records are append-only and
never edited (Stage 1 reproducibility protocol).

### 4.1 Session record

`session_id`, `task_id`, `repo`, `scaffold`, `scaffold_version`, `model_id`, `decoding_params`,
`seed`, `run_id`, `git_commit`, `benchmark_version`, `harness_version`, `container_image_digest`,
`start_ts`, `end_ts`, `wall_time_s`, `n_model_calls`, `total_prompt_tokens`,
`total_completion_tokens`, `total_tool_calls`, `estimated_cost_usd`, `termination_reason`
(solved / step-limit / cost-limit / crash / timeout), **`Y_success`**, `evaluator_score`,
`evaluator_raw`.

### 4.2 Step record

`step_id`, `session_id`, `ts`, `elapsed_s`, `model_call_index`, `prompt_tokens`,
`completion_tokens`, `context_length_tokens`, `cumulative_completion_tokens`,
`cumulative_cost_usd`, `action_type`, `command_text_hash`, `command_normalized_hash`,
`tool_output_bytes`, `tool_output_hash`, `exit_status`, `error_category`, `stderr_head_hash`,
`test_invocation_bool`, `tests_passed`, `tests_failed`, `files_changed_count`, `diff_line_count`,
`repeated_command_k` (times this normalized command appeared in the prefix),
`repeated_error_k`, `action_entropy_so_far`, `model_latency_ms`.

### 4.3 Grey-box (A′) and white-box (B) extensions

A′: `mean_token_logprob`, `min_token_logprob`, `output_entropy`, `top1_margin` — recorded only
where the provider exposes them, with an explicit `logprobs_available` flag.
B (Plan A only): `probe_layer`, `probe_feature_vector_ref`, `probe_score`, `gpu_mem_mb`,
`gpu_util_pct`, `inference_ms`.

### 4.4 Data hygiene

Commands and outputs are stored as **hashes plus bounded-length heads**, never full
environment dumps. No credentials, no environment variables, no file contents beyond diff
statistics. Raw text is retained only for the sampled subset used for manual error-category
validation, and reviewed before release.

---

## 5. Outcome and progress labels

**Primary outcome.** `Y_success` = benchmark evaluator verdict (SWE-bench hidden test suite).
Binary, reproducible, no human judgement.

**Caveat recorded now:** SWE-bench pass/fail has known validity criticisms — UTBoost
(2506.09289, U), AgentLens "lucky pass" (2605.12925, U), SWE-ABS (2603.00520, U). We use the
standard evaluator for comparability and treat "lucky passes" as a labelled-noise source in
limitations, not as something to silently correct.

**Progress proxies** — all must be online-computable:

| Proxy | How measured | Online? | Task-general? | Gameable / leakage risk |
|---|---|---|---|---|
| Fraction of visible tests passing | parsed from agent's own test invocations | Yes, **only when the agent chooses to run tests** | Partly | **High**: agent controls when tests run; presence of a test run is itself informative and confounds with strategy |
| Failing-test count trend | same | Same caveat | Partly | High |
| Compilation / import success | exit status of agent's commands | Yes | Yes | Medium |
| Unresolved-error count | distinct error signatures still recurring | Yes | Yes | Medium |
| Diff size / churn | files changed, lines changed | Yes | Yes | Low |
| Repeated-command ratio | normalized command repeats / total | Yes | Yes | Low |
| Distance-to-gold-patch | diff vs. reference patch | **NO — Class C** | — | **Analysis only** |

**Non-monotonicity is assumed, not hoped for.** *Failure as a Process* (2607.09510, V1) finds
successful agents also err and recover. Any analysis that treats a progress proxy as monotone is
invalid by construction. Recovery is modelled explicitly in §7.

---

## 6. Actionability analysis

### 6.1 Checkpoints

At cumulative **generated-token** deciles of a *pre-declared per-task budget cap* (not of the
realized trajectory): 5, 10, 20, 30, 40, 50, 60, 70, 80, 90% of cap. Because the cap is fixed in
advance and identical for all sessions, this index is fully online. Secondary indexing by model
call count and wall-clock is recorded for robustness.

### 6.2 Predictor ladder

- **Model A (trivial):** elapsed compute, model calls, context length. *This is the baseline the
  signal must beat.* RQ3.3 is decided here.
- **Model B (behavioral, Class A):** A + tool failures, error categories, repeated commands,
  repeated errors, action diversity, test outcomes, diff churn.
- **Model C (richer):** sequence model over step embeddings. **Only if B materially beats A** —
  Stage 1 protocol item 7 (simple before complex) applies.
- **Model A′ (grey-box):** B + logprob/entropy features, where available.
- **Model D (white-box probe):** linear probe on hidden states. **Plan A only** (§10).

Classifiers: logistic regression with L2, then gradient-boosted trees. Nothing deeper without
justification.

### 6.3 Metrics

AUROC, AUPRC, Brier score, calibration (reliability curve + ECE), and **recall at a fixed
false-abort rate** — the operational metric, since a false abort destroys a task that would have
succeeded. Model comparison uses DeLong's test for correlated AUROCs.

### 6.4 The actionability window — **use existing terminology**

**Do not invent a metric name.** This is the *early classification of time series* (ECTS)
problem, which has a mature literature on the accuracy–earliness trade-off, including TEASER's
harmonic mean of accuracy and earliness and ECEC's cost-based stopping rules (Springer/ScienceDirect
sources, U — **must be read before use**). We adopt ECTS framing and cite it.

Pre-declared criterion, fixed **before** data collection:

> `t_predict` = the earliest checkpoint at which the predictor achieves **recall ≥ 0.70 for the
> failure class at a false-abort rate ≤ 0.05**, sustained at that checkpoint and all later ones.

Rationale for these numbers, stated in advance: a 5% false-abort rate is the largest loss of
successful tasks a system could plausibly justify, since aborts are user-visible and terminal;
0.70 recall is the point at which the majority of doomed compute becomes addressable. Both are
arguable — what matters is that they are fixed now.

> `remaining_compute_fraction` = compute remaining after `t_predict` / total compute consumed by
> that session class.

**Actionability requires both** a met quality criterion and meaningful remaining compute. A
predictor reaching AUROC 0.95 at 95% of budget is worthless; AUROC 0.80 at 15% is valuable.

---

## 7. Counterfactual recovery-curve experiment

This is the RQ3.5 experiment and the most important measurement in the project.

### 7.1 The methodology already exists — and comes with a warning

**"The Replay Gap: Static Evaluation of Model Switching in LLM Agents Scores the Wrong World"**
(2608.08239, V1, **accepted at COLM 2026**) forks live SWE-bench agent trajectories at controlled
decision points, rebuilds environment state, and continues each fork — with **control forks using
identical models to isolate baseline noise and sampling variance**. Its findings bear directly on
our feasibility:

- **74–77% of early model swaps diverge at the first post-fork action, versus 6–35% of controls.**
- Static replay leaves "only 3% of replayed states valid."
- Five outcome flips appeared only in swap arms, never across 359 control forks.

**Implications we must accept, not work around.**
1. **Static replay is invalid.** We must re-execute forward, never substitute logged outputs.
2. **Our design is the control arm** (same model, varying *budget*), where divergence is
   6–35% — tractable but far from zero. **Recovery curves will be noisy and replicate-hungry.**
3. **The branching-rollout protocol is prior art.** We *use and cite* it; we do not claim it.

Related infrastructure, all **U**, to be read before implementation: Crab (2604.28138),
Shepherd (2605.10913, overlay checkpoints reportedly 157–252 ms vs. `docker commit` ~2.8× higher
baseline), Causal Agent Replay (2606.08275, V1 — counterfactual *attribution*, not budget
response), Toward Systems Foundations for Agentic Exploration (2510.05556, U, which warns CRIU
and container commits are "not fast enough").

### 7.2 Protocol

At checkpoint `t` for a session: snapshot the container (`docker commit`) and truncate the
message list to the prefix. Then run continuations under budget levels
`b ∈ {1, 2, 4, 8, remaining}` additional model calls, with **R independent seeds each**, plus a
**mandatory control arm** at `b = remaining` reproducing the original configuration, used to
measure our own replay fidelity.

Record per continuation: success, compute used, steps used, trajectory divergence
(first-divergent-step index, normalized edit distance to the original continuation), and a
recovery-type label.

### 7.3 Estimating heterogeneity — the analysis that actually decides RQ3.5

With R = 5 replicates, a per-state estimate of P(success) has a standard error up to 0.22.
**Per-state point estimates are therefore useless and must not be reported as such.** The
correct test is a **variance-component analysis**: fit a mixed-effects logistic model
`success ~ log(budget) + (log(budget) | state)` and ask whether the **random-slope variance is
significantly greater than zero**. Heterogeneity of marginal value is a population-level claim,
tested with many states × few replicates — not few states × many replicates.

This is why the design allocates ~40 states × 3 budget levels × 5 replicates rather than
10 states × 5 × 20.

---

## 8. Measurement questions M1–M10

M1 compute consumed by ultimately unsuccessful sessions · M2 `t_predict` per signal class ·
M3 `remaining_compute_fraction` · M4 Model B vs Model A (DeLong) · M5 white-box earliness gain
(Plan A only) · M6 cross-session heterogeneity of recovery slope (§7.3) · M7 within-session
change in marginal value · M8 whether failed sessions are merely longer or structurally different
(matched on length) · M9 fraction of failed sessions still recoverable after first observable
error · M10 **oracle upper bound** on reallocatable compute.

**M10 is an upper bound under perfect information and must be labelled Oracle everywhere.** It is
not achievable savings. (Stage 1 rule on Oracle reporting applies.)

---

## 9. Sample size and phasing

### 9.1 Power analysis (Hanley–McNeil)

For AUROC `A` with `n` per class, `SE = sqrt([A(1−A) + (n−1)(Q1−A²) + (n−1)(Q2−A²)] / n²)`,
`Q1 = A/(2−A)`, `Q2 = 2A²/(1+A)`. At `A = 0.75`:

| n per class | SE | 95% CI half-width |
|---|---|---|
| 100 | 0.034 | ±0.068 |
| 150 | 0.028 | ±0.055 |
| 200 | 0.024 | ±0.048 |

**Target: ≈150 per class → ≈300 sessions at a ~50% pass rate.** This resolves a true 0.75 from a
trivial-baseline 0.60 with non-overlapping intervals. DeLong's paired test on correlated AUROCs
has more power than these marginal intervals, so 300 is adequate for M4 and is the binding
requirement.

### 9.2 Phases

| Phase | Scope | Purpose | Gate to proceed |
|---|---|---|---|
| **0** | 5–10 tasks, 1 model | Infrastructure: does instrumentation capture every field? Is the record reproducible? Does fork/restore work at all? | Byte-identical re-run under fixed seed where the provider permits; all schema fields populated |
| **1** | ~60 tasks × 2 models | Pilot: measure realized pass rate, trajectory length, cost per session; confirm outcome balance near 50% | Pass rate in [0.35, 0.65]; cost per session within budget |
| **2** | ~300 sessions | Main prediction study (RQ3.1–3.4) | — |
| **3** | ~40 states × 3 budgets × 5 seeds ≈ 600 continuations | Recovery curves (RQ3.5) | Replay-fidelity control arm divergence consistent with the 6–35% range from 2608.08239 |

**Splits are at TASK level** (by repository, then task id), fixed by hash before any modelling.
All continuations forked from a task inherit that task's split. Cross-split leakage of
continuations is the single most likely way to fake a good result here.

Pilot results may not be inspected and then used to re-tune hypotheses without a
`docs/research_log.md` entry (Stage 1 protocol item 5).

---

## 10. Hardware plan

### 10.1 Audited local environment (2026-08-29)

| Component | Finding | Consequence |
|---|---|---|
| CPU | Intel i7-1355U, 10 cores / 12 threads, 1.7 GHz base (low-power U-series) | Adequate for harness, slow for containers |
| RAM | 15.7 GB total, **3.7 GB free at audit** | Tight; SWE-bench containers need headroom |
| Disk | 930 GB, **687 GB free** | Ample for images and traces |
| GPU | **Intel UHD integrated only. `nvidia-smi` NOT FOUND.** | **No CUDA. Plan A is infeasible locally** |
| Python | `python`/`python3` resolve to the Windows Store stub; no `pip`, no `conda` | Not usable as-is |
| **uv** | **0.11.19 present** | **Solves the Python problem** — `uv` can provision an interpreter and environment |
| Docker | CLI present, **daemon not running** (`dockerDesktopLinuxEngine` pipe missing) | Startable; required for both benchmarks |
| WSL2 | Ubuntu present, stopped | Recommended execution environment |
| git, node | present | fine |

### 10.2 Plan B — no local GPU (**primary plan**)

Hosted API model as the agent's LLM; mini-SWE-agent and SWE-bench evaluation in Docker under
WSL2 Ubuntu. Signals: **Class A everywhere; Class A′ where the provider exposes logprobs.**
Class B is **out of scope** on this path. RQ3.2 is answered as "not measurable locally" rather
than guessed.

### 10.3 Plan A — GPU available (**requires external resource**)

Needs a CUDA GPU with ≥24 GB (a 7–8B open-weight model served with vLLM, hidden states captured
at a chosen layer). Options: university cluster allocation, or short-term cloud rental for the
white-box arm only. **Plan A should be attempted only after Plan B has produced Class-A results**,
so the white-box arm answers a question we already know matters.

### 10.4 Throughput note

A 12-thread U-series laptop with ~4 GB free RAM will be the bottleneck for containerized
evaluation long before API rate limits are. Budget for a modest cloud VM for Phase 2/3 execution,
or expect multi-day wall-clock runs.

---

## 11. Cost plan

Anchors, all **U** and to be re-verified before spending: SWE-bench trajectories reportedly run
30–80 turns and 30–75k tokens; GPT-5-class per-instance cost reported around $2.5 (≈$1,250 for
500 instances); a Gemini-2.0-Flash-class run on a 50-task SWE-bench Verified Mini subset reported
at $4.72 (≈$0.09/instance).

| Phase | Sessions / continuations | Cheap-model estimate | Mid-tier estimate |
|---|---|---|---|
| 0 | 10 | $1–3 | $10–25 |
| 1 | 120 | $12–36 | $120–300 |
| 2 | 300 | $30–90 | $300–750 |
| 3 | ~600 partial continuations | $30–120 | $150–400 |
| **Total** | | **≈$75–250** | **≈$580–1,475** |

**Pre-commitments.** (a) No paid API call until a written budget cap is recorded in
`research_log.md`; (b) model selection targets ~50% pass rate, which is *also* the cheap option —
the statistical and financial incentives align, and this is declared before results;
(c) a hard per-phase spend cap enforced in the harness, not by attention.

---

## 12. Falsification criteria (pre-registered)

| ID | Kill condition | Pre-declared threshold |
|---|---|---|
| **K1** | Behavioral prediction useful only after most compute is spent | `t_predict` (Class A) > 70% of budget. *Threshold set at 70%, not 80%, because beyond ~70% too little remains to reallocate to be worth a scheduler* |
| **K2** | Trajectory features do not beat trivial proxies | Model B vs. Model A AUROC gain < 0.05 with DeLong p > 0.05 at every checkpoint ≤ 50% |
| **K3** | Recovery curves show little cross-session heterogeneity | Random-slope variance in the §7.3 mixed model not significantly > 0 (LRT, α = 0.05) |
| **K4** | Marginal value near-identical across sessions | Interquartile range of per-state recovery slope < 20% of its median |
| **K5** | Useful prediction requires white-box access **and** that access is impractical | Class A fails K1/K2 while Class B passes, and probe extraction adds > 10% serving overhead |
| **K6** | Counterfactual forking is not reproducible enough | Control-arm divergence materially worse than the 6–35% band reported by 2608.08239, or control-arm outcome flip rate > 10% |

**Decision rule.** K3 **or** K4 alone ⇒ **do not build the scheduler** (no allocation problem
exists). K1 **and** K2 together ⇒ the C1 thesis is falsified. K6 ⇒ RQ3.5 is unanswerable by this
method; report the methodological finding and stop rather than substituting a weaker proxy.

---

## 13. Reproducibility protocol

```
data/raw/         immutable JSONL trajectories, write-once, hash-manifested
data/processed/   regenerable feature tables (never hand-edited)
configs/          resolved configs, one per run
scripts/          collection, feature extraction, analysis
results/          model outputs, figures, tables (regenerable by logged command)
```
Every run records git commit + dirty flag, resolved config, model id and decoding params, seed,
benchmark and harness version, container image digest, environment capture, timestamp, and run
id. Processed data must be reconstructible from raw by one command. Task-level splits fixed by
hash before modelling. **Any post-hoc change to features, thresholds, or checkpoints is logged in
`research_log.md` with the pre-change result.**

---

## 14. Top methodological risks

1. **Class-C leakage.** The most likely way to produce an exciting, wrong result. Mitigated
   structurally (§2.1), not by care.
2. **Fork divergence swamping the recovery signal.** 6–35% control divergence (2608.08239) may
   exceed the budget effect we are trying to measure. This is K6 and it is a real possibility.
3. **Outcome imbalance.** A 74/26 split halves effective power; hence the deliberate
   weaker-model choice, declared in advance.
4. **Benchmark label validity.** "Lucky passes" and SWE-bench contamination criticisms
   (2605.12925, 2506.09289, 2603.00520 — all U) mean `Y_success` is noisy.
5. **Provider non-determinism.** Hosted APIs are not reproducible at the token level even at
   temperature 0; Phase 0's determinism gate must be stated as "reproducible to within measured
   variance," not "byte-identical."
6. **Hardware.** No GPU, 3.7 GB free RAM, and a stopped Docker daemon stand between this design
   and its first datapoint.
7. **Field velocity.** Three of the papers cited here appeared this month. A literature re-check
   is mandatory before writing.

---

## 15. Outcome decision tree

| Outcome | Condition | Action |
|---|---|---|
| **A** | Early Class-A signal **and** heterogeneous recovery value | Proceed to success-aware allocation design. **New novelty review first** |
| **B** | Only Class-B (white-box) works early | Direction becomes white-box scheduling / serving co-design. Requires GPU access **and** a fresh novelty review — the deployability story narrows to self-hosted models |
| **C** | Prediction works, recovery values homogeneous (K3/K4) | **Do not build a scheduler.** Measurement result only |
| **D** | Prediction arrives too late (K1+K2) | C1 thesis falsified. Possible negative-result paper: *why trajectory-level failure prediction does not translate into resource scheduling* — publishable only if the evidence is strong and the ECTS framing is done properly |
| **E** | No useful predictive signal at all | **STOP the direction.** |

Outcomes C, D, and E are scientifically informative and were the reason to run Stage 3 before
building anything. Outcome A is the only one that authorizes a scheduler.
