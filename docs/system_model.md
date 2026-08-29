# System Model

Status: Stage 1 specification. **Nothing here is implemented yet.** This document is
the contract that the Stage 2 simulator must satisfy; where it says ASSUMPTION, the
choice is a modelling decision that could be revisited (and any revision is logged in
`docs/research_log.md`).
Last updated: 2026-08-23.

---

## 1. Overview

We model a single cluster serving a stream of agentic workflow requests. A central
scheduler assigns *ready tasks* to *workers* drawn from a CPU pool and a GPU pool.
Tasks may fail stochastically; failure triggers retry and, depending on semantics,
invalidation of dependent work. Time advances by discrete events.

```
   arrivals ──▶ [ Workflow Instances ]
                      │  (realized DAG grows at runtime)
                      ▼
              [ Ready Queue ] ──▶ [ Scheduler ] ──▶ [ CPU pool | GPU pool ]
                      ▲                                     │
                      └──────── retry / repair / expand ◀────┘
                                (on failure or completion)
```

---

## 2. Entities

| Entity | Role | Key state |
|---|---|---|
| `SimulationClock` | Virtual time; monotonically non-decreasing | `now` |
| `EventQueue` | Priority queue of future events, ordered by `(time, seq)` for determinism | events |
| `WorkflowTemplate` | Static spec: task types, dependency structure, branch/loop constructs, resource classes, runtime and failure distributions | immutable |
| `WorkflowInstance` | One realized execution of a template | `workflow_id`, arrival time, realized DAG, status |
| `Task` | One schedulable node of a realized DAG | see §3.2 |
| `Attempt` | One execution of a task on a worker | `attempt_id`, start, end, outcome, worker |
| `Resource` / `WorkerPool` | CPU pool and GPU pool of homogeneous workers | capacity, busy set |
| `Scheduler` | Policy under test; chooses assignments at decision points | policy state |
| `FailureModel` | Draws attempt outcomes | parameters, RNG stream |
| `Estimator` | Supplies *predicted* runtime and failure probability to policies that are allowed them | model, training data |
| `MetricsRecorder` | Records every state transition to an event log | append-only log |

**ASSUMPTION A1.** One scheduler, one cluster, no network topology, no data-transfer
time between tasks in v1. Data-movement cost is a known omission (§9).

---

## 3. Workflow Model

### 3.1 Templates (may contain loops) vs. realized execution (a DAG)

This distinction is central and is a frequent source of confusion in workflow
scheduling papers, so we fix it explicitly:

- A **`WorkflowTemplate` is a control-flow graph.** It may contain *branches*
  (conditional successors) and *bounded loops* (retry/repair/critic-revise cycles,
  e.g. "generate → test → if fail, revise → test → ..."). It is **not** a DAG and is
  never scheduled directly.
- A **`WorkflowInstance` produces a realized execution DAG.** Each time a loop body
  is entered or a branch is taken, *new task nodes are instantiated* and appended.
  A revision of a step is a **new node** (`task_type = revise`, iteration index `k`),
  not a mutation of the old node. Therefore the realized structure is always acyclic.
- The realized DAG is **not known in advance.** It is revealed incrementally as
  branch conditions resolve and failures occur. This is what makes the problem online
  rather than a static DAG-scheduling problem.

**Consequence for baselines (fairness requirement).** Policies that reason about the
critical path (CPF, Workflow-Aware) must compute it over the **realized-so-far DAG
plus the template's *expected* remaining structure**, not over the eventual realized
DAG (which is only knowable in hindsight). Using the eventual DAG would be an oracle.
The exact information set for each policy is specified in §7.3.

**ASSUMPTION A2.** Loops are bounded by a maximum iteration count per template; a
workflow that exhausts it terminates in a declared terminal state (§4.3).

### 3.2 Task attributes

Fields the simulator is expected to carry (final field list fixed in Stage 2):

*Identity and structure*
- `task_id`, `workflow_id`, `task_type` (e.g. `llm_infer`, `retrieve`, `tool_call`,
  `code_exec`, `verify`, `revise`)
- `dependencies` (upstream task ids in the realized DAG)
- `iteration_index` (which loop iteration produced this node), `parent_task_id`
  (the node this is a retry/revision of, if any)

*Resource and timing*
- `resource_type` in {CPU, GPU}
- `actual_runtime` — sampled ground truth, **visible only to the simulator**, never
  to a non-oracle policy
- `predicted_runtime` — what an estimator supplies to policies allowed to use it
- `arrival_time` (workflow arrival), `ready_time`, `start_time`, `end_time`

*Failure*
- `failure_probability` — ground-truth parameter, **simulator-only**
- `predicted_failure_probability` — estimator output, visible to permitted policies
- `retry_count`, `retry_budget`

*Metadata*
- `priority` / policy scratch space (must not be used to smuggle ground truth)

**INVARIANT I1.** No scheduler may read `actual_runtime` or `failure_probability`
except an explicitly named Oracle policy. This is enforced structurally: the
scheduler interface receives a `TaskView` object exposing only permitted fields
(§7.2), not the internal `Task`.

### 3.3 Workload generation

- Workflow arrivals: Poisson process with rate `lambda` (ASSUMPTION A3; heavier /
  bursty arrival processes are a planned sensitivity).
- Task runtimes: per-`task_type` distribution (lognormal is the working default,
  ASSUMPTION A4 — chosen for positive support and heavy-ish tail; to be justified or
  replaced when real trace data is available).
- Template families: defined in Stage 2 *before* ReSched is implemented, and to
  include at least one family that is adversarial to failure-aware scheduling
  (e.g., failures concentrated at leaves, where early surfacing buys nothing).

---

## 4. Task Lifecycle

### 4.1 States

```
        PENDING ──(all deps satisfied)──▶ READY ──(scheduler assigns)──▶ RUNNING
                                            ▲                              │
                                            │                              ▼
                                            │                  ┌──── outcome draw ────┐
                                            │                  ▼                      ▼
                                            │              SUCCEEDED                FAILED
                                            │                  │                      │
                    (retry admitted; new attempt)              │        ┌─────────────┴──────────────┐
                                            └─────────────────────────  │  retry budget remaining?   │
                                                                        └──yes──▲          ▼──no─────┘
                                                                                       ABANDONED
                          INVALIDATED ◀── (upstream failure invalidates completed work)
```

States: `PENDING`, `READY`, `RUNNING`, `SUCCEEDED`, `FAILED` (attempt-level),
`INVALIDATED`, `ABANDONED`.

### 4.2 Transitions and their events

| Event | Trigger | Effect |
|---|---|---|
| `WORKFLOW_ARRIVAL` | arrival process | instantiate instance; entry tasks → READY |
| `TASK_READY` | last dependency SUCCEEDED | task enters ready queue |
| `TASK_START` | scheduler assignment | worker reserved; schedule `TASK_END` at `now + actual_runtime` |
| `TASK_END` | timer | draw outcome → SUCCEEDED or FAILED; release worker |
| `TASK_RETRY` | FAILED and budget remains | new `Attempt` (a new node in the realized DAG per §3.1) |
| `TASK_ABANDONED` | FAILED and budget exhausted | terminal; workflow outcome per §4.3 |
| `INVALIDATE` | upstream failure under semantics that invalidate | affected SUCCEEDED/RUNNING work marked INVALIDATED |
| `WORKFLOW_END` | all sink tasks terminal | record TCT |

**ASSUMPTION A5 (fail-stop at completion).** A failure is detected *when the attempt
ends*, i.e. the full `actual_runtime` is consumed before failure is observed. This is
the pessimistic, and we believe most realistic, case for verifier-style failures
(you must run the tool/model to learn it failed). Early-detected failures
(failure at time `f < runtime`) are a planned variant, because they change the waste
accounting materially.

**ASSUMPTION A6 (non-preemptive).** A running task runs to completion; it is never
preempted or killed. Preemption/kill is a natural extension and an obvious
alternative mechanism for the same goal, so its absence must be stated as a
limitation when comparing against speculative-execution literature.

### 4.3 Terminal workflow outcomes

- `COMPLETED` — all sink tasks SUCCEEDED.
- `FAILED_OUT` — some task exhausted its retry budget and the template declares no
  fallback. Such workflows must be **counted and reported separately**, never
  silently dropped from TCT statistics (dropping them would bias TCT downward for
  exactly the policies that cause more abandonment).

---

## 5. Retry and Invalidation Semantics

Three mechanisms are distinguished. **Only mechanism (a) is enabled in v1;
(b) and (c) are configurable variants (`INVAL`) used to test H3/H6 sensitivity.**

**(a) Local retry (v1 default).** The failed task is re-executed as a new attempt.
Completed upstream results remain valid. Downstream tasks had not started (they were
not READY), so nothing is invalidated. Cost of a failure = re-execution of that task +
delay to everything downstream.

**(b) Sub-DAG invalidation.** A failure at task `t` invalidates a declared set of
already-completed descendants or siblings (e.g., a verifier rejecting a plan
invalidates work produced from that plan). Those tasks must be re-executed. This is
where "downstream recomputation cost" becomes non-trivial and is the mechanism H3
targets.

**(c) Repair / revise.** Failure spawns a *different* task type (`revise`) rather than
re-running the identical task, possibly with different runtime and failure
distributions (e.g., a revise step conditioned on the error message may be more
likely to succeed than a naive retry).

**Open modelling questions (to resolve in Stage 2, with justification recorded):**

- Are retry attempts i.i.d., or does success probability change across attempts?
  A naive i.i.d. model implies geometric retry counts; real agent retries plausibly
  either improve (error feedback) or are correlated (a fundamentally impossible task
  never succeeds). We will parameterize this explicitly rather than assume i.i.d.
  by default, since it directly controls how much retry amplification exists to
  optimize away.
- Are failures independent across tasks, or correlated within a workflow (a "hard"
  instance fails everywhere)? Correlation changes what a predictor can learn.
- Does a retry cost the same as the original attempt? (Caching, warm state.)

---

## 6. Resource Model

- Two pools: `CPU` with `N_cpu` homogeneous workers, `GPU` with `N_gpu` homogeneous
  workers.
- A task requires exactly one worker of its `resource_type` for its whole runtime
  (ASSUMPTION A7: no multi-worker tasks, no fractional/shared occupancy, no
  GPU-sharing or batching in v1).
- No task migration; no preemption (A6).
- Scheduling is **work-conserving unless a policy deliberately chooses otherwise**.
  ReSched may deliberately leave a worker idle (deferring risky work). This is an
  allowed and interesting behaviour, but it must be *explicitly declared* by the
  policy and counted, because non-work-conserving policies can lose badly at low
  load, and hiding this would misrepresent the trade-off.
- Zero placement cost in v1 (no cold start, no model load time). **ASSUMPTION A8**;
  model-load / warm-cache effects are a plausible follow-up because they interact
  strongly with re-execution cost.

---

## 7. Scheduler Interface

### 7.1 Decision points

The scheduler is invoked when, and only when, one of these occurs:
task becomes READY, task completes (worker freed), workflow arrives, or an
invalidation event changes the ready set. Scheduler wall-clock time per invocation is
recorded as `sched_overhead`. Simulated time does **not** advance during a scheduling
decision in v1 (ASSUMPTION A9); if measured overhead turns out to be non-trivial
relative to task runtimes, we must revisit this and charge it in simulated time.

### 7.2 Interface sketch (final signature fixed in Stage 2)

```python
class Scheduler(Protocol):
    def schedule(
        self,
        now: float,
        ready: Sequence[TaskView],
        free_workers: Mapping[ResourceType, int],
        ctx: SchedulingContext,
    ) -> Sequence[Assignment]:
        """Return zero or more (task_id, resource_type) assignments.

        Invariants the simulator enforces on the return value:
          - every task_id appears at most once
          - every assigned task is in `ready`
          - assignments per resource class do not exceed `free_workers`
          - the scheduler cannot observe simulator-private ground truth
        """
```

`TaskView` exposes only permitted fields (I1). `SchedulingContext` exposes the
realized-so-far DAG, template metadata, queue state, and — for policies permitted
them — estimator outputs.

### 7.3 Information sets per policy (fairness contract)

| Policy | May use |
|---|---|
| FIFO | arrival/ready order only |
| SJF | + `predicted_runtime` |
| Critical-Path-First | + realized-so-far DAG and template expected remaining structure |
| Resource-Aware | + resource availability, per-class queue state, `resource_type` |
| Workflow-Aware | + workflow-level state (progress, remaining work, per-workflow slack) |
| ReSched | + `predicted_failure_probability`, expected downstream recomputation cost |
| Oracle-ReSched | + ground-truth `actual_runtime`, `failure_probability`, and realized outcomes. **Diagnostic upper bound only. Never a deployable system. Never used to support a performance claim.** |

**Fairness rule.** Any information item made available to ReSched that a baseline
could realistically also have (e.g., `predicted_runtime`) **must** be made available
to that baseline too. If ReSched wins only because it alone sees runtime estimates,
that is a confound, not a contribution.

### 7.4 ReSched priority function (design sketch, NOT yet validated)

The intended shape is a priority combining (i) urgency/critical-path contribution,
(ii) failure probability, and (iii) expected downstream recomputation cost, e.g.
schematically `priority(t) = f(slack(t), p_fail(t), E[downstream_invalidated_work(t)],
resource_scarcity(t))`. **The exact functional form is deliberately left open here.**
It will be specified, ablated (each term removed in turn), and justified in Stage 4 —
and the ablation is what determines whether the failure term is actually doing the
work, or whether an incidental SJF/CPF bias is (see H2 falsification).

---

## 8. Invariants (to be asserted in code and unit-tested)

- **I1** Ground truth (`actual_runtime`, `failure_probability`, future outcomes) is
  unreachable from any non-oracle policy.
- **I2** Conservation: for every worker, sum of busy intervals ≤ measurement window,
  and busy intervals never overlap.
- **I3** Capacity: concurrently RUNNING tasks per class ≤ pool capacity, always.
- **I4** Dependency safety: a task starts only after all its dependencies are
  SUCCEEDED and not INVALIDATED.
- **I5** Acyclicity: the realized execution graph is a DAG at all times.
- **I6** Monotonic time: events are processed in non-decreasing time order, with a
  deterministic tie-break (`seq`) so that runs are reproducible.
- **I7** Determinism: identical (config, seed, code version) ⇒ byte-identical event
  log.
- **I8** Accounting closure: every resource-second is attributed to exactly one
  category (useful / invalidated / retried / idle) — this is what makes §10 possible.
- **I9** Termination: every workflow reaches a terminal state, or the run is flagged.

---

## 9. Known Fidelity Limitations (bound every claim we make)

1. No data transfer / communication cost.
2. No cold start, model load, or cache warmth effects.
3. No preemption or task killing (A6) — relevant when comparing to speculative
   execution.
4. No batching or GPU sharing; token-level inference dynamics are abstracted away.
5. Failures detected only at completion (A5) in v1.
6. Homogeneous workers within a class.
7. Synthetic workloads: no validation against a real agentic trace yet. **This is the
   single largest threat to external validity and must be stated in any write-up.**
8. Single scheduler, single cluster, no multi-tenancy or admission control.

---

## 10. OPEN: Definition of "Wasted Compute" — **NOT FINALIZED**

Per the research protocol, this definition is **deliberately not fixed in Stage 1**.
It is the most manipulable metric in the study: several defensible definitions exist
and they favour different policies.

Candidate definitions:

- **W-A (re-execution work).** Resource-seconds consumed by attempts that did not
  produce a result used by the completed workflow (failed attempts + invalidated
  successes). Ignores idleness. Favours policies that avoid starting risky work, even
  by idling.
- **W-B (W-A + deliberate idleness).** W-A plus resource-seconds a work-conserving
  policy would have used but a deferring policy left idle. Penalizes ReSched's
  deferral; arguably the fairer "total cost to the operator" view.
- **W-C (excess over an ideal).** Total resource-seconds minus the resource-seconds
  of a hypothetical failure-free execution of the same realized useful work.
  Requires defining the ideal reference, which is itself contestable.

Edge cases that any chosen definition must be tested against **before** it is used:

1. A task that fails after 99% of its runtime vs. one that fails immediately.
2. Work invalidated *while still running* (partially-consumed occupancy).
3. Work completed for a workflow that is later `FAILED_OUT` — is *all* of it waste?
4. A `revise` task that reuses the failed attempt's output as input — the failed
   attempt was not useless.
5. Idle workers under a deliberately non-work-conserving policy.
6. Retries that were unnecessary because a sibling branch already satisfied the sink.

Plan: implement W-A and W-B, designate one as **primary** in `experiment_plan.md`
*before* running comparisons, report both, and treat sign-flips between them as a
finding about metric sensitivity rather than choosing the flattering one.
