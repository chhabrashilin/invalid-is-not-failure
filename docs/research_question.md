# Research Question

Status: Stage 1 specification (pre-registration). No experiments have been run.
Last updated: 2026-08-23.

---

## 1. Primary Question

**Can failure-aware scheduling reduce end-to-end task completion time and wasted
computation in agentic AI workflows compared with resource-aware and
workflow-aware scheduling policies?**

Decomposed into three sub-questions:

- **RQ1 (Effectiveness).** Does incorporating per-task failure probability and
  expected downstream recomputation cost into scheduling decisions reduce mean
  and tail workflow completion time relative to policies that ignore failure?
- **RQ2 (Conditions).** Under which workload and system regimes does the benefit
  appear, grow, vanish, or reverse? (failure rate, workflow depth/width, offered
  load, CPU/GPU mix, contention)
- **RQ3 (Robustness).** How much does the benefit degrade as failure-probability
  estimates degrade, and at what estimation quality does failure-aware scheduling
  stop being worth its complexity?

RQ2 and RQ3 are first-class. A result of the form "it helps everywhere" would be
more suspicious than a result of the form "it helps in regime X and not in regime Y."

---

## 2. Motivation

Agentic AI applications differ from conventional single-shot inference serving
because satisfying one user request can require many dependent operations:
model inference, retrieval, tool execution, code execution, verification /
critic steps, and external API calls.

Three properties of this workload class motivate the question:

1. **Stochastic failure is routine, not exceptional.** Tool calls time out,
   generated code fails to compile or execute, verifier steps reject an output,
   external APIs rate-limit, and structured-output parsing fails. Retry is a
   normal control-flow path rather than an error path.
2. **Failure is not local.** When a step fails and is retried or repaired, work
   that has already executed downstream of (or speculatively alongside) it may be
   invalidated. The cost of a failure therefore depends on *where in the workflow
   it happens*, not only on the failed task's own runtime.
3. **Resources are scarce and heterogeneous.** GPU workers are the scarce class;
   CPU-bound tool/retrieval steps and GPU-bound inference steps interleave. A
   scheduler that commits a scarce GPU to work with a high probability of being
   invalidated pays twice: once for the wasted occupancy and again for the
   re-execution.

Conventional DAG schedulers (FIFO, SJF, critical-path-first) and resource-aware
schedulers optimize an objective that implicitly assumes tasks succeed. If failure
probability is both non-trivial and *predictable* (even coarsely, from task type
and historical statistics), then that information is available to a scheduler at
decision time and is currently unused.

**Whether exploiting it actually helps, and by how much, is an empirical question
this project intends to answer — including the possibility that it does not.**

---

## 3. Scope

In scope for this project:

- A **discrete-event simulator** of an agentic workflow execution environment with
  CPU and GPU worker pools.
- **Workflow templates** that may contain branches and bounded loops (retry /
  repair / critic-revise cycles), and the **realized execution DAGs** those
  templates produce at runtime.
- **Task-level stochastic failure** with retry and downstream invalidation
  semantics.
- A **scheduler interface** implemented by several independent policies: FIFO,
  Shortest-Job-First, Critical-Path-First, Resource-Aware, Workflow-Aware,
  ReSched (proposed), and Oracle-ReSched (diagnostic bound only).
- **Metrics**: workflow Task Completion Time (TCT) distribution (mean, P50, P95,
  P99), throughput, CPU/GPU utilization, scheduler decision overhead,
  fairness/starvation, retry amplification, and wasted compute.
- **Sensitivity analysis** across failure rate, depth, width, load, resource mix,
  and estimator error.
- **Reproducibility infrastructure**: seeded runs, saved configs, raw run-level
  outputs, environment capture.

Deliberately deferred (candidate future stages, not commitments):

- Trace-driven validation against a real agentic workload trace, if a suitable
  public trace can be obtained and its licence permits.
- A thin real-system prototype (e.g., a scheduling shim over a local worker pool)
  to sanity-check the simulator's qualitative conclusions.

---

## 4. Explicit Non-Goals

The following are **not** goals of this project, and no claims will be made about them:

1. **Not a production scheduler.** No Kubernetes operator, no vLLM integration, no
   cloud deployment, no cluster autoscaling.
2. **Not an agent framework.** We do not propose how to write agents, prompt them,
   or improve their task success rate. Failure probability is an *input* to this
   work, not something we try to reduce.
3. **Not LLM quality research.** No claims about answer accuracy, hallucination, or
   model capability. A "failure" here is an execution-level event, not a judgement
   about output quality beyond what a modelled verifier step decides.
4. **Not GPU kernel / inference-engine optimization.** We do not model batching,
   KV-cache, paged attention, or token-level scheduling in v1. GPU workers are
   modelled at task granularity.
5. **Not multi-tenant fairness research.** Fairness/starvation is measured as a
   guardrail metric to detect pathologies, not optimized as an objective.
6. **Not an optimality proof.** We do not claim ReSched is optimal. Oracle-ReSched
   is an empirical diagnostic under perfect information, not a theoretical bound.
7. **Not a claim about real hardware performance.** Every number produced in
   Stage 2+ is a simulator output unless explicitly labelled otherwise.

---

## 5. Novelty Hypothesis — **UNVERIFIED**

> **This section is a working belief, not an established claim. It has NOT been
> checked against the literature; no literature search has been performed yet. It
> must be verified in the related-work stage before it appears in any paper draft,
> and it may well be refuted.**

Working belief (unverified):

- **N1 (UNVERIFIED).** Classical DAG/workflow scheduling (list scheduling,
  critical-path methods, HEFT-style heuristics) and cluster schedulers for ML
  workloads generally treat task failure as an exception handled by re-execution
  *after* the fact, rather than as a *scheduling signal available before* the fact.
- **N2 (UNVERIFIED).** Fault-tolerant scheduling and speculative-execution work
  (straggler mitigation, checkpoint/restart placement) targets a different failure
  model — infrastructure/node failure and stragglers — than *semantic,
  task-type-correlated failure*, where a verifier or tool rejects the output and
  forces re-execution or repair of a *sub-DAG*.
- **N3 (UNVERIFIED).** The specific combination of (i) per-task failure
  probability, (ii) expected *downstream invalidation* cost, and (iii)
  heterogeneous CPU/GPU resource cost, folded into a single online scheduling
  priority for agentic workflows, has not been evaluated.

**Falsification of novelty is a valid and useful outcome.** If N1–N3 turn out to be
well covered by existing work, the correct response is to reposition the
contribution (e.g., as an empirical characterization of *when* failure-awareness
matters for agentic workloads) rather than to restate the claim more vaguely.

Novelty-verification checklist to complete before any paper draft:

- [ ] DAG/workflow scheduling under uncertainty
- [ ] Fault-tolerant and speculative scheduling in data-parallel systems
- [ ] ML/DL cluster scheduling literature
- [ ] LLM inference serving and agent-serving systems
- [ ] Stochastic scheduling / scheduling with uncertain processing times
- [ ] Reliability-aware scheduling in grid/cloud/HPC
- [ ] Record every near-miss in `docs/related_work.md` with the exact distinction

---

## 6. What Would Make This Study Credible

Pre-committed standards (detail in `docs/experiment_plan.md`):

1. Baselines are implemented independently and given every piece of information
   they could realistically have. A baseline is not allowed to be weak by neglect.
2. Any regime where a baseline beats ReSched is reported, not buried.
3. ReSched parameters are fixed before the reporting runs, or the tuning procedure
   is described and performed on configurations disjoint from the reported ones.
4. Every number in the paper traces to a raw run-level artifact under `results/`
   and a command recorded in `docs/research_log.md`.
5. The "wasted compute" metric definition is fixed and stress-tested on edge cases
   *before* it is used to compare policies.

---

## 7. Terminology (working definitions; refined in `system_model.md`)

| Term | Working definition |
|---|---|
| Workflow template | Static specification of an agentic workload; may contain branches and bounded loops. |
| Workflow instance | One realized execution of a template; produces a DAG that grows at runtime. |
| Task | One schedulable unit of a workflow instance; occupies exactly one worker. |
| Attempt | One execution of a task; a task may have multiple attempts due to retries. |
| Failure | An attempt that terminates without producing a valid result, per `system_model.md`. |
| Invalidation | The event by which already-completed work becomes unusable because of an upstream failure. |
| TCT | Task/workflow Completion Time; the primary metric, defined precisely in `experiment_plan.md`. |
| Wasted compute | **Definition intentionally NOT finalized in Stage 1.** See `system_model.md` §10. |
