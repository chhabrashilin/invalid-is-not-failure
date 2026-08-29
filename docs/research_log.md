# Research Log

Append-only. Newest entries at the bottom. Every methodology change, failed idea,
anomaly, and post-hoc decision goes here with a reason and a date.

Entry template:

```
## YYYY-MM-DD — <short title>
**Stage:** <n>
**What changed:**
**Why:**
**Impact on prior results:**
**Commands:**
```

---

## 2026-08-23 — Stage 1: research specification and repository initialization

**Stage:** 1

**Starting state.** `resched/` was a git repository on branch `master` with **no
commits**, no remotes, and empty directories `docs/ simulator/ scheduler/ experiments/
analysis/ tests/ results/ paper/`. Only `docs/research_question.md` (research question
+ motivation) and `docs/hypotheses.md` (H1–H6 prose plus an unstructured list of
candidate variables) had content. `README.md`, `requirements.txt`, `.gitignore`,
`docs/system_model.md`, `docs/experiment_plan.md`, `docs/related_work.md`, and
`docs/research_log.md` were empty (0 bytes). **No Python source existed.**

**What changed.**

- `docs/research_question.md` — kept the existing question and motivation; added RQ1–RQ3
  decomposition, scope, seven explicit non-goals, a novelty hypothesis (N1–N3)
  **explicitly labelled UNVERIFIED with a verification checklist**, credibility
  standards, and a terminology table.
- `docs/hypotheses.md` — restructured H1–H6, each with independent variables, dependent
  variables, controls, named confounders, a **falsification criterion fixed in
  advance**, and an explicit "what we conclude if it is not supported" clause. The
  loose variable list at the end of the previous version was formalized into the
  factor-space table (§0.1). Added cross-cutting threats to validity.
- `docs/system_model.md` — created. Entities, workflow model, the
  **template-with-loops vs. realized-execution-DAG distinction**, task lifecycle state
  machine and event table, retry/invalidation semantics (three mechanisms; only local
  retry enabled in v1), resource model, scheduler interface with a **per-policy
  information-set table**, nine machine-checkable invariants, known fidelity
  limitations, and an **open section for the "wasted compute" definition**.
- `docs/experiment_plan.md` — created. High-level only: staging with exit criteria,
  metric definitions (with the waste metric explicitly unresolved), experiment families
  E0–E8 each tied to a hypothesis, the E0 validation suite, statistical protocol,
  reproducibility protocol, fairness-to-baselines protocol, pre-committed reporting
  rules, and known gaps. **No results, no numeric outcomes.**
- `docs/related_work.md` — created as an explicitly empty stub with a search checklist
  and search-log table. **Zero citations, deliberately** — none will be added except
  from papers actually located and read.
- `README.md`, `.gitignore`, `requirements.txt` — created.
- `.gitkeep` markers added to `simulator/ scheduler/ experiments/ analysis/ tests/
  results/ paper/` so the structure is tracked by git (git does not track empty
  directories).

**Key decisions recorded (all revisable, all logged if revised).**

1. **The "wasted compute" definition is deliberately left open.** Three candidate
   definitions (W-A re-execution work, W-B including deliberate idleness, W-C excess
   over an ideal) and six edge cases are documented in `system_model.md` §10. Rationale:
   it is the most manipulable metric in the study; fixing it after seeing results would
   invalidate H6. Plan: implement W-A and W-B, designate the primary **before** any
   policy comparison, report both, treat sign-flips as a metric-sensitivity finding.
2. **Structural enforcement of the no-leakage rule (I1).** Policies receive a
   `TaskView`, not the internal `Task`, so ground-truth `actual_runtime` and
   `failure_probability` are unreachable rather than merely "not used." Oracle-ReSched
   is the only exception and is designated diagnostic-only.
3. **Fairness-to-baselines rule.** Any information given to ReSched that a baseline
   could realistically have must be given to that baseline too (e.g., predicted
   runtime). Otherwise a win is a confound.
4. **Critical-path baselines must use the realized-so-far DAG plus the template's
   *expected* remaining structure**, never the eventual realized DAG — using the latter
   would silently make them oracles.
5. **Pre-committed adversarial experiment (E8)** and **ablation (E7)** were added to
   the plan before any implementation, so that a positive H1 is falsifiable and credit
   for any gain can be attributed to the failure term specifically.
6. **v1 modelling assumptions** deliberately pessimistic/simple and labelled A1–A9:
   non-preemptive, fail-stop detected only at task completion, one worker per task, no
   data movement, no cold start, no batching.

**Impact on prior results:** none — no results exist.

**Unresolved / risks carried forward.**

- **No Python interpreter is installed on this machine** (`python`, `py`, and
  `python3` all resolve to the Windows Store stub). This blocks Stage 2. Requires a
  real CPython install (3.11+) before the simulator can be built or tested.
- `requirements.txt` lists unpinned dependencies; exact pins + a lock/`env.json`
  capture must be produced at the first experiment run (protocol item 4).
- Novelty claims N1–N3 are unverified; `docs/related_work.md` is empty by design.
- Workload realism is unvalidated against any real agentic trace — currently the
  largest external-validity threat.
- No commits existed in the repo at the start of this stage; the initial commit has
  not been made by this milestone (left to the user's discretion).

**Commands:** see the milestone report for the exact command list
(`ls`, `cat`, `find`, `git status`, file writes).

---

## 2026-08-23 — Stage 1 audit: adversarial review of the specification

**Stage:** 1 (review)

**What changed:** No files modified. A skeptical-reviewer audit of the Stage 1 spec was
performed and produced four critical findings, recorded here because they drive Stage 2:

- **C-1.** Under the v1 local-retry-only semantics with per-(workflow, task, attempt) common
  random numbers, the number of attempts and each attempt's runtime are fixed by the draw
  sequence independent of scheduling order. Total and failed-attempt resource-seconds are
  therefore **policy-invariant**, making H6 a guaranteed null and leaving no mechanism for
  the paper's central claim to act on.
- **C-2.** "Failure-aware scheduling" was never defined as an intervention, and covers at
  least three mutually inconsistent strategies (run risky work early / defer risky work /
  inflate expected work by the retry multiplier).
- **C-3.** The strongest baselines — retry-adjusted SJF and retry-adjusted critical path —
  were absent, and may subsume the proposal.
- **C-4.** H1's falsification criterion is conditioned on a default operating point that
  Stage 3 would have chosen *after* seeing pilot behaviour, and carries no minimum effect
  size, contradicting the reporting rule in `experiment_plan.md` §5.

Also recorded: utilization used as both IV and DV; failure probability trivially learnable
because it is a deterministic function of task type in the generator; depth used as a proxy
for invalidation blast radius; scheduler overhead uncharged in simulated time (A9) while
ReSched is the most expensive policy; abandonment selection bias in completed-only TCT;
P99 claims unpowered (workflows-per-run never fixed); synthetic workloads overgeneralized.

**Why:** To decide whether to build the simulator. Verdict was conditional-go on the
semantics-agnostic simulator core, no-go on experiments or claims.

**Impact on prior results:** none — no results exist.

---

## 2026-08-23 — Stage 2: adversarial literature review

**Stage:** 2

**What changed:** `docs/related_work.md` rewritten from an empty stub into a literature
matrix of 30 works with per-entry verification levels, a search log, the three special
tests, and a closest-competitor analysis. No other Stage 1 documents were modified, because
the findings force a reformulation that should be made deliberately rather than incrementally.

**Method:** ~20 search themes across agent serving, LLM inference scheduling, stochastic and
reliability-aware DAG scheduling, speculative and optimistic execution, transactional memory,
lineage/recomputation, sequential testing, and agentic workload characterization. Publisher or
arXiv landing pages were fetched directly for every entry marked V1/V2; entries confirmed only
via publisher/index pages are marked V3 and entries confirmed only via search text are marked
**U**. Eight open verification debts are listed in `related_work.md` §8.

**Findings that change the project:**

1. **The retry-adjusted expected-work idea is classical.** Ordering by cost-to-failure-
   probability ratio is the standard result in sequential testing and pipelined filter
   ordering, and rework/unreliable-machine scheduling is a mature OR subfield. Strategies A
   and C from the audit are **baselines, not contributions**. A 2026 paper (arXiv:2606.07589)
   re-proving the ratio rule without citing the classics is direct evidence of how easily this
   is rediscovered.
2. **The speculative-validation reformulation is already occupied.** Sherlock
   (arXiv:2511.00330, Nov 2025) speculatively executes downstream agent-workflow nodes while
   verification runs in the background, rolls back to the last verified output, chooses
   verifier placement, and uses an explicit expected-cost model over the speculated set. Six
   further 2025–2026 preprints (PASTE, SPORK, Speculative Actions, DSP, Speculate-with-Memory,
   Cost-Aware Speculative Execution) occupy adjacent ground.
3. **The mechanism itself is 40 years old.** Time Warp / Virtual Time (Jefferson, TOPLAS
   1985) is optimistic execution with cascading invalidation of speculative descendants.
4. **The contention question was answered for a different speculation model.** Hopper
   (SIGCOMM 2015) co-designs speculation with cluster scheduling under capacity; Yoo & Lee
   (SPAA 2008) throttle speculative concurrency under contention feedback. Neither involves a
   semantic validator or an invalidation cascade.
5. **One assumption is shared by every agent-speculation paper found and is false under
   load:** speculation is treated as free because it runs in otherwise-idle resource
   (arXiv:2607.12236 states this explicitly). Sherlock evaluates on a dedicated 8×A100 with one
   workflow at a time and reports no GPU utilization or idle-capacity measurement.
6. **The agent-serving schedulers we should have used as baselines model no failure at all.**
   Autellix/Agentix (NSDI 2026), SAGA, Helium, InferCept, Preble — none model failure,
   verification, or invalidation. Our Stage 1 baseline list (FIFO/SJF/CPF) was far weaker than
   the real state of the art.
7. **Evidence grading for agent-specific claims** (`related_work.md` §6): CPU/GPU
   interleaving, burstiness, tool-call failures, retry/recovery loops, and KV-state behaviour
   are **MEASURED** in production studies. But the two properties our method most depends on —
   that failure probability is predictable, and that retries are non-i.i.d. — have **no
   measured support in anything found**.

**Decision recorded:** recommendation is **PIVOT**, not GO and not STOP. The speculative-
validation direction as stated is occupied; the surviving gap is the multi-tenant
capacity-allocation question layered on it. Full decision in the Stage 2 milestone report
(sections A–J), to be reviewed before any Stage 1 document is rewritten.

**Impact on prior results:** none — no results exist. Stage 1 documents
(`research_question.md`, `hypotheses.md`, `system_model.md`, `experiment_plan.md`) are now
known to be partly invalid (H1–H6 as written, the baseline set, and the v1 retry semantics)
but were deliberately left unmodified pending the reformulation decision.

**Unresolved / carried forward:** the eight verification debts in `related_work.md` §8, the
most important being (a) reading Sherlock's evaluation directly to confirm the no-contention
claim on which the entire gap rests, and (b) reading PASTE's full text, since "avoid shifting
the bottleneck to the GPU" is the closest published statement of the proposed contribution.
Python is still not installed on this machine.

**Commands:** web searches and page fetches only; file writes to `docs/related_work.md` and
`docs/research_log.md`. No code was written and no experiments were run.

---

## 2026-08-23 — Stage 2B: full-text prior-art verification and pivot kill test

**Stage:** 2B

**What changed:** `docs/related_work.md` gained a `# Stage 2B Full-Text Kill Test` section
(§2B.1–2B.8). No other document modified. `research_question.md`, `hypotheses.md`,
`system_model.md`, and `experiment_plan.md` remain byte-identical to Stage 1 as instructed.

**Method:** full-text fetches (HTML and PDF) of Sherlock, PASTE, Cost-Aware Speculative
Execution, Atomix, Autellix, SAGA, and Hopper, plus four targeted searches outside the
AI-agent literature (PDES optimism control, decision-dependent stochastic RCPSP, cascading
rollback under resource constraints, speculative-vs-non-speculative scheduling theory) and
three on KV-cache contention in agentic serving.

**Findings that ended the direction:**

1. **T1 SUPPORTED.** Sherlock is single-workflow on a statically partitioned 8×A100 with no
   arrival process, no queueing, no multi-tenancy, and no utilization or throughput metric.
   Its Eq. 4/6/8 assume `lat_exec`/`lat_vrf` are constants and its budget `B` is exogenous
   and per-workflow. Contention is genuinely absent.
2. **T2 only PARTIALLY SUPPORTED — this is what killed the gap.** PASTE already owns the
   entire contention half: authoritative vs. speculative job classes, slack/opportunistic
   budgeting, preemption of speculative work when authoritative work needs resources, an
   interference-priced priority term including queue/batch and KV pressure, 32 A100s, and a
   replayed bursty Azure Functions arrival trace. Only semantic validation and sub-DAG
   cascade are missing. The candidate contribution reduces to substituting Sherlock's
   Eq. 6 cost into PASTE's existing scheduler.
3. **T3 SUPPORTED but signposted.** No system combines both terms — but Cost-Aware
   Speculative Execution §14.2 explicitly declares the contended-capacity regime out of
   scope and names "B-PASTE's interference term (µ·ΔI)" as the right hook, left
   unimplemented. The gap is a published to-do item, not an unnoticed hole.
4. **T4 REFUTED.** Optimism control in optimistic parallel discrete-event simulation is the
   same optimization problem: bound speculative advance (Moving Time Window `[GVT, GVT+w]`)
   to limit expected **cascading** rollback under finite processors and memory, with adaptive
   online estimation of rollback overhead. Cascade depth under contention — the property we
   believed was distinctive — is that literature's defining concern.
5. **T5 SUPPORTED**, but only via continuous batching (GPU service cost non-separable across
   co-batched requests), which is a property of the resource model rather than of the
   speculation/validation mechanism that was to be the contribution.
6. The fallback idea considered mid-review — speculative work evicting other tenants' KV
   cache and forcing *their* recomputation — was checked and is also occupied:
   Continuum/CacheTTL (arXiv:2511.02230) prices exactly "reload cost and potential queueing
   delay induced by eviction," alongside TokenCake, KVFlow, CacheCast, and SAGA's TTL.

**Decision:** applying the pre-committed rule without softening — T4 REFUTED, T2 only
partial, T5's surviving property not attached to the proposed mechanism — the verdict is
**STOP** on speculative-validation scheduling for agentic workflows. Three alternative
directions were produced and ranked; the recommended sequence is a measurement study
(agentic goodput accounting) that both de-risks and grounds a subsequent scheduling paper on
doom-detection and abandonment control.

**Methodological anomalies recorded (important for trust in this review):**

- The **Sherlock PDF** extraction produced plausible-looking but generic equation
  descriptions that conflicted with the HTML full text. Only HTML-derived equations were
  recorded. This is a live example of why extraction output must be cross-checked.
- **PASTE returned two materially different scheduling formulations** across two fetches of
  the same arXiv ID (a knapsack-style program vs. a ratio priority function with no formal
  program). Both are recorded; only what they agree on was used.
- **Hopper's full text could not be extracted** from three PDF sources; all Hopper claims
  remain at bibliographic-confirmation level.
- PDES optimism-control citations are marked **U** (unverified). They are used to *reject*
  our novelty, which is the safe direction for an unverified citation, but must be read
  before appearing in any write-up.

**Impact on prior results:** none — no results exist. The Stage 1 specification is now known
to be built on a direction that has been abandoned; it should be rewritten or archived once
a new direction is chosen, not patched.

**Unresolved / carried forward:** five verification debts in `related_work.md` §2B.8, plus
the eight from Stage 2. Python is still not installed on this machine.

**Commands:** web fetches and searches only; file writes to `docs/related_work.md` and
`docs/research_log.md`. No code written, no experiments run, no numbers generated.

---

## 2026-08-29 — Stage 2C: new paper direction search

**Stage:** 2C

**What changed:** New file `docs/stage2c_candidate_directions.md` (landscape, six candidates,
score table, kill test, execution risks). The abandoned ReSched specification files
(`research_question.md`, `hypotheses.md`, `system_model.md`, `experiment_plan.md`) were **not**
modified, per instruction. `related_work.md` was not modified either — Stage 2C findings live
in the new file to keep the abandoned direction's record separate from the new search.

**Central finding.** The August 2026 literature is split into two halves that do not
communicate:

- **Half A — trajectory science, single-session, no resource model.** Failure as a Process
  (2607.09510: 1,794 annotated trajectories, 7 models, 3 scaffolds, 63k steps, builds no
  system); Doomed from the Start (2607.06503: activation probes, **abort/continue only**, no
  allocation, no reallocation of saved compute); Early Diagnosis of Wasted Computation
  (2606.01365: 58.1% of tokens in warned failed runs are spent after the first warning, single
  system, identical resource caps); Bayesian Self-Escalation (2608.24087: optimal stopping, no
  contention, no switching cost); TRIAGE (2605.13414: benchmark, sequential, not concurrent
  serving); Recovering Wasted Compute in Autoresearch Agents (2608.10424: agent design, single
  agent).
- **Half B — agent serving systems, real resource model, blind to task success.** SAGA,
  Continuum/CacheTTL, MARS, TOPAS, Autellix/Agentix, GoodServe, Helium. **None uses any signal
  about whether the session will succeed.** MARS names the "engine activity vs. workflow
  progress" gap but defines progress as latency critical path.

**Terminology hazard recorded.** "Goodput" is already taken in LLM serving: it means
SLO/latency-attaining throughput (GoodServe, 2605.16867, uses it this way). A success-based
metric must be named differently — this project will use **task goodput** if it proceeds.

**Areas checked and rejected as crowded:** recovery-action selection (Self-Healing Agentic
Orchestrators 2606.01416 already conditions recovery choice on remaining recovery budget;
SHIELDA); context compaction / checkpoint economics (Slipstream, Self-Compacting, Beyond
Compaction, context-rot); KV-cache scheduling for agents (saturated); model routing and
cascades (2608.24087 landed 2026-08-25, four days before this review).

**Candidates and scores** (unweighted mean, 10 = good on every axis including inverted ones):
C1 task-goodput scheduling **7.2**; C2 cost geometry of agent sessions **7.2**; C6 task-goodput
accounting **6.7**; C4 tool-failure amplification **6.6**; C3 escalation under switching cost
**6.0**; C5 recovery-action selection **5.3**. C1 and C2 tie numerically but differ in shape
(high-ceiling/high-risk vs. low-ceiling/low-risk) and are complementary halves of one project.

**Decision:** **GO on a scoped kill-test**, not on the full mechanism. Recommendation is C1
with C2/C6 as its measurement half and fallback. Before any scheduler is built, one
measurement must settle a **direct contradiction inside Half A**: Failure as a Process reports
that failures "often remain hidden until recovery is no longer possible," while Doomed from the
Start reports prediction "from the first interaction round." Both cannot be generally true. If
the signal is not actionable early, C1's mechanism is dead and the result is a negative finding
worth publishing; if it is, the mechanism is justified.

**Explicitly carried as UNVERIFIED (the Stage 2B lesson applied):** the four structural
properties claimed to separate C1 from bandits/optimal stopping — escalating marginal cost with
context growth, non-free arm switching via KV eviction, non-monotone progress, and
abort/deprioritize asymmetry — are **PLAUSIBLE BUT UNVERIFIED**. Stage 2B died from asserting
an analogous structural claim without measuring it. These must be measured before they are
used to defend novelty.

**Impact on prior results:** none — no results exist.

**Unresolved / blocking:** (1) **Python is still not installed** on this machine; (2) **GPU
access is unknown** and determines whether C1's strong form is feasible; (3) trace-collection
API budget is unbudgeted; (4) the field moves in weeks — a literature re-check is mandatory
before writing anything.

**Commands:** web searches and page fetches only; file writes to
`docs/stage2c_candidate_directions.md` and `docs/research_log.md`. No code written, no
experiments run, no numbers generated.

---

## 2026-08-29 — Stage 3: measurement design and signal-actionability kill test (DESIGN ONLY)

**Stage:** 3

**What changed:** New file `docs/stage3_measurement_design.md` (20 sections). No data collected,
no code written, no paid API calls, no dependencies installed, no scheduler designed. Abandoned
ReSched spec files untouched.

**Correction adopted from the user, and it changes the design.** Stage 2C wrongly claimed
*Failure as a Process* (2607.09510) and *Doomed from the Start* (2607.06503) were contradictory.
They are not: the first concerns **externally observable** failure signals arriving late, the
second concerns **internal activation** signals arriving early. Both can hold. The design now
separates four signal classes throughout — A (black-box, scheduler-observable), A′ (grey-box:
logprobs/entropy from some hosted APIs), B (white-box: hidden activations), C (oracle/post-hoc,
never deployable). If A is late and B is early, success-aware scheduling is feasible **only for
self-hosted open-weight models**, which is the most consequential possible finding and is now an
explicit outcome branch (Outcome B).

**Platform selected: mini-SWE-agent + SWE-bench Verified** (primary); Harbor + Terminal-Bench 2.0
(backup, 89 tasks). Chosen on a 12-criterion score (102 vs 95 vs 87 vs 77), not popularity. The
decisive properties: mini-SWE-agent's history is linear and "there's no difference between the
trajectory and the messages that you pass on to the LM," it is bash-only with one action type,
and it is ~100 lines — so instrumentation is auditable and forking is list-truncation plus
container restore. SWE-bench Verified gives a deterministic hidden-test oracle over 500 instances.

**Pre-declared design decisions (recorded now so they cannot later look like outcome-shopping):**

1. **Model chosen to target a ~50% pass rate.** mini-SWE-agent reportedly exceeds 74% on
   SWE-bench Verified with strong models; a 74/26 split badly weakens prediction statistics. A
   weaker/cheaper model maximizes power and minimizes cost simultaneously.
2. **`t_predict` criterion fixed in advance:** earliest checkpoint with failure-class recall
   ≥ 0.70 at false-abort rate ≤ 0.05, sustained thereafter.
3. **Checkpoints indexed by cumulative consumed resource against a fixed pre-declared budget
   cap**, never by fraction of realized trajectory length (that is Class C / future information).
4. **Class C excluded structurally**, not by discipline: feature extraction receives a prefix
   object that cannot address events at index > t. Same enforcement idea as Stage 1 invariant I1.
5. **Sample size 300 sessions (~150/class)** from a Hanley–McNeil calculation: SE 0.028, 95% CI
   half-width ±0.055 at AUROC 0.75 — enough to separate a real 0.75 from a trivial-baseline 0.60.
6. **Task-level splits fixed by hash before modelling**; all continuations inherit their task's
   split. Continuation leakage across splits is the easiest way to fake a good result.

**Prior art that constrains the methodology (found this stage, and it matters).**
*The Replay Gap* (2608.08239, accepted at COLM 2026) already publishes the branching-rollout
protocol we intended to design — fork at step k, rebuild environment, re-execute forward, with
same-model control forks to isolate sampling noise. Three consequences: (a) the protocol is
**prior art we cite and use, not something we claim**; (b) **static replay is invalid** — it
reports only 3% of replayed states valid, so continuations must be re-executed forward, never
spliced; (c) **control-arm divergence is 6–35%**, which is our noise floor and may swamp the
budget effect. That last point became falsification criterion K6.
Also recorded (all U, to be read before implementation): Crab (2604.28138), Shepherd
(2605.10913), Causal Agent Replay (2606.08275), Systems Foundations for Agentic Exploration
(2510.05556, which warns CRIU and container commits are "not fast enough").

**Terminology corrected.** The actionability window is the **early classification of time series
(ECTS)** problem, which already has accuracy–earliness trade-off metrics (TEASER's harmonic mean,
ECEC's cost-based stopping rules). We adopt and cite that framing rather than inventing a metric
name. STRE and MCV remain internal placeholders, explicitly not claimed as novel.

**Heterogeneity analysis specified correctly.** With 5 replicates a per-state P(success) estimate
has SE up to 0.22, so per-state point estimates are useless. RQ3.5 is therefore tested as a
**variance-component question** — mixed-effects logistic model with a random slope on
log(budget), testing whether random-slope variance > 0 — which is why the design uses many states
× few replicates (≈40 × 3 × 5) rather than few states × many replicates.

**Hardware audit (decisive).** i7-1355U, 10c/12t; 15.7 GB RAM with only 3.7 GB free; 687 GB free
disk; **Intel UHD integrated graphics only — `nvidia-smi` NOT FOUND, no CUDA**; Docker CLI
present but daemon not running; WSL2 Ubuntu present but stopped; git and node present. **`uv`
0.11.19 is installed — this resolves the Python blocker carried since Stage 1** (the Store stub
remains unusable, but uv can provision an interpreter).
Consequence: **Plan A (white-box, local open-weight serving) is infeasible on this machine.**
Plan B (hosted API model + Class A/A′ signals) is the primary path; RQ3.2 will be answered as
"not measurable locally" rather than guessed. Plan A requires an external GPU (≥24 GB) and should
be attempted only after Plan B produces Class-A results.

**Cost plan:** ≈$75–250 with a cheap model, ≈$580–1,475 mid-tier, across four phases.
**Pre-commitment: no paid API call until a written budget cap is recorded in this log**, plus a
hard per-phase spend cap enforced in the harness rather than by attention.

**Falsification criteria K1–K6 pre-registered** with thresholds, including the decision rule that
K3 or K4 alone (homogeneous recovery curves) means **do not build the scheduler**, because no
allocation problem would exist.

**Impact on prior results:** none — no results exist.

**Unresolved / blocking before Phase 0:** (1) start Docker daemon and WSL2, provision Python via
uv; (2) confirm free RAM is sufficient for SWE-bench containers (3.7 GB free at audit is
marginal); (3) select the model and record the target pass rate and budget cap in this log;
(4) read the six U-marked methodology papers before implementing the fork protocol;
(5) re-check literature — three cited papers appeared this month.

**Commands:** local environment audit (`Get-Command`, `Get-CimInstance`, `uv --version`,
`docker info`, `wsl -l -v`), web searches and page fetches, and file writes to
`docs/stage3_measurement_design.md` and `docs/research_log.md`. No installs, no paid API calls,
no experiments, no generated numbers.

---

## 2026-08-29 — Stage 4 / Phase 0: infrastructure validation — **PASS**

**Stage:** 4 (Phase 0). First implementation milestone. No scheduler, no predictive model, no
Phase 1, no scientific claim. Stage 3 thresholds and hypotheses are UNCHANGED.

### Cost authorisation

At the start of Phase 0 this log contained **no `PHASE_0_API_BUDGET_USD` line**, so under the
Phase 0 cost rule **no paid API call was permitted and none was made**. Phase 0 ran entirely on
a deterministic mock LM. Every mocked session records `model_id` with a `mock:` prefix so mocked
runs can never be mistaken for real trajectories in later analysis.

**PHASE_0_API_BUDGET_USD = 0.00** (declared retrospectively as the *actual* Phase 0 spend, which
was zero. This line does NOT authorise future spend: Phase 1 requires its own budget line, to be
written before any paid run.)

### Version control fixed first

The repository had had **no commits since Stage 1**. Before writing any code:
`aa9ce83` — *Archive research design through Stage 3* on `master`, deliberately preserving the
abandoned ReSched direction as research provenance. Work then proceeded on branch
`phase0-infrastructure`.

### What was built

`pyproject.toml` + `uv.lock` (Python 3.12.13 via uv; pydantic/pyyaml/docker/pytest only —
**no torch/CUDA**, since there is no NVIDIA GPU and swebench's base deps exclude it);
`src/trajectory/{schema,features,store}.py`; `src/instrumentation/{recorder,mock_lm,agent_loop}.py`;
`src/checkpoint/docker_env.py`; `src/evaluation/evaluator.py`; `scripts/phase0/{select_instance,run_phase0}.py`;
`configs/phase0/*`; 48 tests; `docs/phase0_runbook.md`; `docs/phase0_report.md`.

### Result: PASS on all twelve criteria (P0.1–P0.12)

Real SWE-bench instance image (4.16 GB), 6-step instrumented session, `docker commit` checkpoint
at a pre-declared step, three restored continuations, independent evaluator, all raw artifacts
hash-manifested and re-verified. 48/48 tests pass.

### The bug Phase 0 existed to find

**Run 001's evaluator was silently invalid.** It reported `success=false, tests_passed=null`
because pytest returned *"no tests ran"* (exit 4): the FAIL_TO_PASS node ids
`test_separable[compound_model6-result6]` / `[compound_model9-result9]` are parametrisations that
**only exist after the instance `test_patch` is applied**, and the harness had skipped that step.
Had this reached Phase 1 it would have labelled every one of ~300 sessions a failure and produced
a confident, entirely fictitious "prediction" result.

Fixed by `apply_test_patch()`: reset test files to `base_commit` (so an agent cannot edit the
tests it is judged by), `git apply` the instance test patch, then evaluate. Run 002 then
discriminated correctly — parent (fix applied) **2 passed → success=True**; all three forks
(no fix) **2 failed → success=False**.

**Run 001's flawed raw data was retained, not deleted or edited**, and run 002 used a new
`run_id`, per the immutability rule.

### Instance selection (pre-declared, success-blind)

Rule fixed and written to `configs/phase0/selected_instance.json` before execution: sort all 500
SWE-bench_Verified `instance_id`s as ASCII ascending, take the first → **`astropy__astropy-12907`**.
Depends only on naming, so it cannot be tuned toward a pass.

### Fork test — what it does and does not show

Same seed (a vs b): **identical**, no divergence. Different seed (a vs c): **divergence detected
at index 0**. All three outcomes `success=False`; fork c diverged in *actions* while matching in
*outcome*, so action divergence does not imply outcome divergence — relevant to how divergence is
measured in Phase 3. **n=3; nothing scientific is claimed.**

**Crucially: with a mock LM there is no provider nondeterminism.** The dominant real source of
fork divergence — 6–35% for same-model control forks per *The Replay Gap* (arXiv:2608.08239) — is
**unmeasured**, so falsification criterion K6 remains entirely open.

### Four measurement defects found (Phase 1 work items, not architecture failures)

1. `docker diff` counts non-agent churn — `b_files_changed_total = 537` at k=3, dominated by
   conda/pytest cache artifacts. Must scope to repository paths or use `git diff --stat`.
2. **Piping destroys exit-status fidelity.** `... | tail -5` made a *failing* pytest run record
   `exit_status=0` and `failed_tool_calls=0`. Real agents pipe constantly; without `pipefail` the
   Model B failure-rate features will be badly biased.
3. Agent-run tests are frequently unparseable, so `test_invocation=False` and `tests_failed=None`.
   Direct evidence for the Stage 3 §5 warning that test-derived progress proxies are agent-controlled
   and high-risk.
4. `python`/`python3` remain the Windows Store stub; everything must go through `uv run`.

### Hardware confirmation

Docker VM: 12 CPUs / 7.58 GB. **No CUDA GPU** — Stage 3 Plan B is confirmed as the route and
Plan A (white-box hidden states) remains infeasible locally. ~4.2 GB per instance image and ~40 s
per fork cycle will not scale to 300 sessions plus forks on this laptop.

### Blockers before Phase 1

(1) Write a Phase 1 budget line before any paid run; (2) fix defects 1–3, which directly corrupt
Model B features; (3) measure real provider fork divergence (K6); (4) integrate mini-swe-agent
proper (2.4.6, requires-python >=3.10) rather than the minimal mirror loop; (5) decide throughput
plan — cloud VM or multi-day local runs; (6) verify RAM headroom beyond ~2 concurrent containers.

**Commands:** see `docs/phase0_runbook.md`. Headline:
`uv sync --group dev` · `uv run python scripts/phase0/select_instance.py` ·
`docker pull swebench/sweb.eval.x86_64.astropy_1776_astropy-12907:latest` · `uv run pytest` ·
`uv run python scripts/phase0/run_phase0.py --config configs/phase0/smoke.yaml`


---

## 2026-08-29 — Stage 4B / Phase 0.5: real-agent measurement pipeline — **MODIFY**

**Stage:** 4B (Phase 0.5). Branch `phase0.5-real-agent-validation` from `a812835`.
No scheduler, no model training, no Phase 1, no scientific claim. Stage 3 falsification
criteria unchanged.

### Cost authorisation — deliberately NOT written

There is **no `PHASE_0_5_API_BUDGET_USD` line in this log**, so no paid API call was made.
I did not add one: authorising spend is the user's decision, not mine.

**Recommended cap when the user decides: `PHASE_0_5_API_BUDGET_USD = 2.00`** — sized for one
real trajectory (~75K tokens, $0.02–0.08 at DeepSeek-V4-Flash/Codestral rates), one checkpoint
and 2–3 continuations, with ~20x headroom. Two independent programmatic enforcement points
already exist (`InstrumentationContext.spend_cap_usd` pre-call check; upstream
`config.cost_limit`, which the adapter tightens but never loosens).

### The blocking discovery

**No LLM API credentials exist anywhere on this machine, and no local inference runtime.**
No `OPENAI_*`/`ANTHROPIC_*`/`GEMINI_*`/`DEEPSEEK_*`/`OPENROUTER_*`/... env vars; no
`~/.config/litellm`, `~/.mini-swe-agent`, or `.env`; no `ollama`/`llama-server`/`lms`/`vllm`
binary; nothing on `localhost:11434`. **Phase 0.5 Steps 9–12 (real agent run, real checkpoint,
real control forks, K6) are therefore not executable here at all** — independently of budget.

### Defect status

| | Defect | Status |
|---|---|---|
| D1 | `docker diff` counted conda/pytest churn (537 "files changed") | **FIXED + TESTED** — `src/instrumentation/repo_state.py`, git-scoped to the repo, with a `measured` flag so a failed measurement is not read as zero |
| D2 | pipeline masked failing exit status | **FIXED + TESTED LIVE** — `set -o pipefail`; in-container proof: `false \| tail -5` → exit 1 with pipefail, exit 0 without |
| D3 | brittle test detection | **FIXED + TESTED** — structural argv classification over 10 frameworks; three-valued status where UNPARSEABLE is never collapsed into NOT_RUN |
| D4 | mirror loop, not mini-SWE-agent | **FIXED** — mini-swe-agent 2.4.6 installed; adapter overrides only the two documented hooks; `require_real_backend()` quarantines mock runs |
| D5 | real-provider fork divergence | **NOT CLOSED — blocked on credentials.** `K6_STATUS = UNTESTED` |
| D6 | local throughput unknown | **BOUNDED, not closed** — measured below |

### Contamination rule (D1)

Agent-change accounting runs **before** the evaluator applies `test_patch`, **and** the
instance test files are passed as `exclude_paths`. Two independent defences, because
attributing the evaluator's own edits to the agent would silently corrupt every repo-change
feature. Tested by `test_d1_test_patch_can_never_be_attributed_to_the_agent`.

### mini-SWE-agent integration approach

Not a fork. Upstream `DefaultAgent.query()` is documented *"Override to add hooks"*; the adapter
subclasses it and overrides `query()` and `execute_actions()` only. Prompt templates, action
parsing, `FormatError` handling, the `run()` loop and message construction remain upstream. A
test asserts the upstream hook docstring still exists so an upstream API change breaks the build
rather than the measurements. Validated with upstream's own `DeterministicModel` +
`LocalEnvironment` — the real agent class runs under instrumentation, `exit 3` is captured
correctly, and the spend cap halts the loop — all at $0.

### Instance selection (pre-declared, committed seed)

`sort by sha256("resched-phase0.5-2026|" + instance_id)`, take first 3 of 500 →
**#1 `matplotlib__matplotlib-23412`**, #2 `django__django-14765`, #3 `astropy__astropy-14096`.
Fall through to #2/#3 only on infrastructure failure; a failed task is a valid outcome.

### Measured local performance (D6)

container start 0.62s · trivial exec 0.83s · `git status` 0.97s · pytest(2 tests) 6.95s ·
**`docker commit` 68.0s** · restore 0.89s · cleanup 1.56s. Docker holds 24.45GB images +
16.87GB build cache.

`docker commit` at 68s is the binding constraint and confirms the Stage 3 warning
(arXiv:2510.05556) that container commits are too slow; Shepherd (arXiv:2605.10913) reports
157–252ms overlay checkpoints. Phase 1 estimate: **300 sessions ≈ 50–125h sequential (2–5 days)**,
~5.7h of checkpointing, $3–30 API, and **~200–400GB of instance images** (fits in 687GB free only
with batching by image plus pruning). Local execution is feasible but slow; no cloud
infrastructure was provisioned.

### New methodological issues

(a) per-step `git status` adds ~1s/step ≈ 80s/session of pure instrumentation overhead — Phase 1
should consider measuring every *k* steps or only after write-plausible commands; (b) renames are
counted once as a modification, documented and tested rather than accidental; (c) upstream
`AgentConfig` requires `system_template`/`instance_template`, so any Phase 1 runner must supply
them.

### Decision: MODIFY

Not PASS — the PASS criteria require a real trajectory, real checkpoint and ≥2 real forks, none of
which are possible without credentials. Not FAIL — nothing found suggests the architecture cannot
support the design; the blockers are procurement and authorisation, not viability.

**Blockers before Phase 1:** (1) provide credentials or a local runtime; (2) write the budget line
and confirm the model; (3) re-run Steps 9–12 on `matplotlib__matplotlib-23412`; (4) complete the
online-feature audit on that real trajectory; (5) decide repo-measurement cadence; (6) plan image
storage/pruning.

**Commands:** `uv add --group agent "mini-swe-agent==2.4.6"` ·
`uv run python scripts/phase0/select_phase05_instances.py` ·
`MSWEA_SILENT_STARTUP=1 uv run --group agent --group dev pytest` (99 passed). No paid API calls.
