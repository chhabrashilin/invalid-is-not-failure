# Stage 2C — Candidate Research Directions

Date: 2026-08-29. Produced after accepting the Stage 2B **STOP** on speculation-under-validation.
Purpose: identify an executable AI-systems research problem for Fall 2026.

**Nothing in this document is a result.** All citations carry a verification level
(V1 = landing page fetched, abstract read verbatim; V2 = full text read; V3 = index/publisher
confirmed; U = search text only).

---

## 1. The August 2026 landscape

The literature has split cleanly into two halves that **do not talk to each other**. This
separation is the central finding of Stage 2C.

### Half A — Trajectory science (single session, no resource model)

| Work | ID | Verif. | What it produces | What it does NOT do |
|---|---|---|---|---|
| Failure as a Process: An Anatomy of CLI Coding Agent Trajectories | 2607.09510 | V1 | 1,794 annotated trajectories, 7 frontier models, 3 scaffolds (OpenHands, MiniSWE, Terminus2), 63,000+ steps, 14 findings. Failures are "predominantly driven by epistemic errors, typically begin within the first few execution steps, and often remain hidden until recovery is no longer possible" | Builds **no system**. Purely characterization |
| Doomed from the Start: Early Abort via a Recall-Controlled Probe Cascade | 2607.06503 | V1 | Linear probes on internal activations predict eventual failure "from the first interaction round"; distribution-free calibrated detector with 90–95% recall targets | **Abort/continue only.** No resource allocation, no scheduling, no multi-tenancy, no reallocation of saved compute, no recovery action other than stopping |
| Early Diagnosis of Wasted Computation in Multi-Agent LLM Systems | 2606.01365 | V1 | "Among warned failed runs, 58.1% of tokens are spent after the first warning on average" (165 GAIA traces) | Single multi-agent system, identical resource caps. **No allocation across concurrent sessions, no serving infrastructure** |
| Knowing When to Ask for Help: Bayesian Self-Escalation | 2608.24087 | V1 | Intra-generation escalation as Bayesian optimal stopping over a learned competence posterior; closed-form myopic threshold; 1/√n regret | **Not a systems paper.** No resource contention, no multi-tenant allocation, no switching/KV cost |
| TRIAGE: Prospective Metacognitive Control under Resource Constraints | 2605.13414 | V1 | Benchmark: can a model triage a task pool under a token budget? Finds "substantial gaps" | **Evaluation benchmark**, sequential planning, not concurrent serving |
| Recovering Wasted Compute in Autoresearch Agents | 2608.10424 | V1 | Agent-design interventions (global debug consultant, tree-search refinement) | Explicitly agent-design, single agent, **no concurrent-session allocation** |

### Half B — Agent serving systems (resource model, but blind to task success)

| Work | ID | Verif. | Optimizes | Failure/success awareness |
|---|---|---|---|---|
| SAGA | 2605.00528 | V1/V2 | Task completion time, fairness, KV reuse | **None.** Assumes all inference steps succeed |
| Continuum / CacheTTL | 2511.02230 | U | Job completion time via KV TTL pinning; prices "reload cost and potential queueing delay induced by eviction" | **None** |
| MARS | 2604.26963 | V1 | End-to-end critical path under coupled GPU–CPU pressure; notes the gap between "engine activity and workflow progress" | Progress = latency critical path, **not task success.** No failure, retry, or abandonment model |
| TOPAS | 2608.25523 | U | Joint prefix-cache retention + request scheduling | **None** |
| Autellix / Agentix | 2502.13965 / NSDI'26 | V1/V2 | Program-level latency (PLAS/ATLAS) | **None**; speculation listed as future work |
| GoodServe | 2605.16867 | V1 | "Goodput" — but **SLO/latency-defined**, i.e. requests meeting end-to-end latency targets | **None.** Does not consider whether the agent task succeeded |
| Helium | 2603.16104 | V1 | Reuse-driven speedup | **None** |

**The gap between the halves.** Half A shows that a large fraction of agent compute is spent
after failure is already determined. Half B builds schedulers that assume every admitted
session deserves to run to completion, and whose best metric — "goodput" — means
*SLO-attaining throughput*, not *successful-task throughput*. **No system found uses a
success-probability signal as a scheduling input.** The term "goodput" is already taken by the
latency-SLO meaning, so any new metric must be named differently (this doc uses **task goodput**).

### Areas checked and found crowded (do not pursue)

- **Recovery-action selection**: Self-Healing Agentic Orchestrators (2606.01416, U) already
  runs monitor→detect→diagnose→recover→verify and "selects recovery actions conditioned on
  execution state and **remaining recovery budget**." Also SHIELDA (2508.07935, U),
  ToolMisuseBench (2604.01508, U), Verified Tool Calls (2608.02645, U).
- **Context compaction / checkpoint economics**: Slipstream (2605.08580, U), Self-Compacting
  LM Agents (2606.23525, U), Beyond Compaction (2606.11213, U), Toward Reliable Context
  Compression (2608.06503, U). Context-rot is a 2026 industry-standard topic.
- **KV-cache scheduling for agents**: saturated (Continuum, TokenCake, KVFlow, CacheCast, TOPAS, SAGA).
- **Model routing/cascades**: FrugalGPT/RouteLLM lineage plus 2608.24087.

---

## 2. Candidate directions

### C1 — Task-goodput scheduling: success-probability-aware capacity allocation across concurrent agent sessions

**Research question.** *Given N concurrent agent sessions sharing fixed inference capacity,
does allocating the marginal unit of compute by estimated marginal probability of task success
per unit cost increase successful task completions per GPU-hour relative to
success-blind schedulers — and is the mid-trajectory success signal actionable early enough
for allocation to matter at all?*

**Systems insight.** Every agent serving system optimizes latency for work it assumes will
succeed; every trajectory paper predicts success for a session it assumes runs alone. Compute
denied to a doomed session is not merely *saved* — it is *transferable* to a session that will
succeed, and the value of that transfer depends on cluster load, which neither half models.

**Nearest prior work.** (1) *Doomed from the Start* (2607.06503) — same signal, but abort-only
and single-session; (2) *Continuum* (2511.02230) — same resource setting, no success signal;
(3) *Bayesian Self-Escalation* (2608.24087) — optimal-stopping over a competence posterior,
single agent, no contention.

**Novelty threat.** A reviewer will say: *"this is Doomed-from-the-Start's probe plugged into a
scheduler — i.e., bandits/knapsack with a predicted reward."* This must be answered with
**structural** properties, not framing. Four candidates, each independently measurable:

1. **Escalating marginal cost.** Context grows monotonically within a session, so the cost of
   "one more step" rises as the session runs — and plausibly rises *faster* for struggling
   sessions, which accumulate error-handling context. Classical bandits assume constant pull cost.
2. **Non-free arm switching.** Deprioritizing a session risks KV eviction and full context
   recompute on resume — Continuum documents session contexts of 70K–200K tokens at session
   end. Classical bandits have free switching.
3. **Non-monotone progress.** Successful agents also err and recover (2607.09510), so the
   signal is not a monotone hazard. A "kill on first failure signal" classifier is provably the
   wrong policy; that is *why* this is a scheduling problem rather than a detection problem.
4. **Irreversibility asymmetry.** Aborting is terminal and user-visible; deprioritizing is not.
   The action space is richer than the binary that Half A studies.

**The scientific tension that makes this worth doing.** Half A contains a direct internal
contradiction. *Failure as a Process* finds failures "often remain hidden until recovery is no
longer possible." *Doomed from the Start* claims prediction "from the first interaction round."
**Both cannot be generally true.** Resolving when the signal becomes actionable — and whether
it arrives early enough to reallocate — is a contribution regardless of sign.

**Minimum viable experiment.** Collect a few hundred agent trajectories on a public benchmark
(Terminal-Bench / SWE-bench-verified) with per-step token, latency, tool-outcome, and
context-length instrumentation. Build a **trace-driven replay harness** (not an invented
workload) that replays real sessions against a modelled fixed-capacity server. Compare
success-blind baselines (FCFS, program-level attained service à la PLAS, shortest-remaining
predicted) against success-aware allocation, measuring successful tasks per GPU-hour and the
latency cost to sessions that would have succeeded.

**Strongest experiment.** Add a live serving loop on open-weight models where the probe is
computed inside the server; measure real end-to-end task goodput under a bursty arrival trace;
report the full cost curve including tasks killed that would have recovered (the false-abort
rate is the metric that makes or breaks deployability).

**What kills it.** (a) The success signal is not actionable until after most compute is already
spent — allocation gains collapse to what abort-only already achieves; (b) success-aware
allocation is indistinguishable from a simple age/context-length heuristic (i.e. the signal adds
nothing beyond "old sessions are bad"); (c) false aborts destroy enough successful tasks that
task goodput falls.

**Note:** (a) and (b) are *publishable negative results* — they would settle the Half A
contradiction and establish that trajectory signals are not schedulable, which the field
currently assumes without evidence.

---

### C2 — The cost geometry of agent sessions

**Research question.** *How does the marginal cost of an additional agent step evolve within a
session, how does it differ between eventually-successful and eventually-failed sessions, and
can an age/context-aware admission and preemption policy exploit that difference without any
learned success predictor?*

**Systems insight.** Agent sessions are not jobs of unknown-but-fixed size; their per-step cost
grows with their own history. If cost growth alone separates successful from failed sessions,
a serving system needs no ML at all — a strictly stronger engineering result than C1.

**Nearest prior work.** *Agentic Coding in the Wild* (2608.00101, V1: 3.2M users, 13M sessions,
761M LLM calls, 95T tokens; KV hit rate ~90% within a turn falling to ~55% across turn
boundaries); *Agentic AI Workload Characteristics* (2605.26297, V1); *Continuum* (2511.02230).

**Novelty threat.** "This is a characterization paper with a heuristic." Real risk. Mitigated
only if the cost-geometry difference is large and the resulting policy is competitive with C1's
learned version — which would be the interesting finding.

**Minimum viable experiment.** Instrument trajectories; fit cost-per-step vs. session age,
split by outcome. **Strongest:** show the age-aware policy captures most of the achievable task
goodput, making learned predictors unnecessary.

**What kills it.** Cost curves for successful and failed sessions are indistinguishable, or the
difference is entirely explained by session length (which is circular).

---

### C3 — Escalation under switching cost and shared capacity

**Research question.** *When a serving system can move a struggling session to a stronger model,
how should the escalation threshold change once the cost of escalation includes KV-state loss
and the capacity taken from other tenants?*

**Nearest prior work.** *Bayesian Self-Escalation* (2608.24087, V1, submitted 2026-08-25 — four
days before this review); RouteLLM/FrugalGPT lineage; commercial trajectory-conditioned routers.

**Novelty threat.** Severe and recent. 2608.24087 already derives the optimal stopping threshold;
our delta is "add switching cost and contention," which is exactly the Stage 2B mistake
(add contention to someone's decision rule). **Do not pursue as a primary direction.**

**What kills it.** Any follow-up to 2608.24087 that adds a cost term — likely within months.

---

### C4 — Tool-failure amplification budgeting

**Research question.** *Can the expected downstream token amplification of a tool failure be
predicted at call time, and should tool invocation policy (timeout, alternative tool, sandbox,
defer) be a resource-management decision?*

**Nearest prior work.** Self-Healing Agentic Orchestrators (2606.01416, U); ToolMisuseBench
(2604.01508, U); Verified Tool Calls under Non-Atomic Failures (2608.02645, U);
MCP-enabled agent performance characterization (2511.07426, U).

**Novelty threat.** The measurement half is largely done and the recovery-selection half is
occupied. The unoccupied piece — *predicting amplification magnitude* — is narrow.

**What kills it.** Amplification is dominated by model identity and task, not by tool identity,
making per-call prediction useless.

---

### C5 — Recovery-action selection as resource allocation

**Research question.** *Should the choice among retry / replan / escalate / reset / abort be made
by a resource manager using expected recovery value per unit cost?*

**Novelty threat.** **Occupied.** Self-Healing Agentic Orchestrators already selects recovery
actions "conditioned on execution state and remaining recovery budget"; SHIELDA structures the
escalation ladder. Listed for completeness; **not recommended.**

---

### C6 — Task-goodput accounting: a measurement methodology and open trace corpus

**Research question.** *What fraction of agent inference compute contributes to successfully
completed tasks, under a definition rigorous enough to be reproducible and hard to game?*

**Systems insight.** The field reports tokens/sec, requests/sec, and SLO-goodput. Nobody reports
the denominator that matters to an operator: useful compute / total compute. Stage 1's audit
established that this metric's *definition* is its hardest part — several defensible definitions
favour different policies.

**Nearest prior work.** 2606.01365 (58.1% of tokens after first warning, single system, 165
traces); 2608.00101 (production scale but proprietary); 2607.09510 (trajectory annotation, no
resource accounting).

**Novelty threat.** "A measurement paper with no mechanism." True — this is a workshop paper on
its own. Its real value is as the **enabler and de-risker for C1**: it produces the traces, the
metric, and the failure/retry statistics that Stage 2 found have *no* measured support anywhere.

**What kills it.** Nothing kills it scientifically; it simply has a low ceiling alone.

---

## 3. Score table

Scale 1–10. For **Literature risk** and **Private-data need**, 10 = GOOD (low risk / little
dependence). Overall = unweighted mean, reported to one decimal.

| Dimension | C1 Task-goodput sched. | C2 Cost geometry | C3 Escalation | C4 Tool amplif. | C5 Recovery sel. | C6 Accounting |
|---|---|---|---|---|---|---|
| Novelty potential | 7 | 6 | 4 | 5 | 3 | 4 |
| Systems depth | 8 | 6 | 7 | 6 | 6 | 4 |
| Empirical tractability | 7 | 9 | 7 | 8 | 7 | 9 |
| Implementation tractability | 6 | 9 | 6 | 8 | 6 | 9 |
| Literature risk (10 = low) | 6 | 6 | 3 | 5 | 3 | 5 |
| Private-data need (10 = low) | 8 | 9 | 8 | 8 | 8 | 9 |
| Time to first result | 6 | 9 | 6 | 8 | 6 | 10 |
| Paper upside | 8 | 5 | 6 | 5 | 4 | 4 |
| Grad-school research signal | 9 | 6 | 7 | 6 | 5 | 6 |
| **Overall** | **7.2** | **7.2** | **6.0** | **6.6** | **5.3** | **6.7** |

C1 and C2 tie numerically but differ in shape: C1 is high-ceiling / high-risk, C2 is
low-ceiling / low-risk. They are **complementary halves of one project**, not competitors —
C2 is the measurement contribution and the fallback if C1's mechanism fails.

---

## 4. Prior-art kill test (applied to C1, the recommended direction)

| # | Question | Answer |
|---|---|---|
| 1 | What is genuinely new? | Using an online success-probability signal as a **capacity-allocation input across concurrent sessions**, with task goodput (successful tasks per GPU-hour) as the objective. No system found does this; Half A stops at abort, Half B never sees the signal |
| 2 | "Just paper X plus agents"? | The nearest X is *Doomed from the Start*, and the criticism has force unless the four structural properties (escalating cost, non-free switching, non-monotone progress, action asymmetry) are **measured and shown to change the policy** |
| 3 | "Just bandits / optimal stopping / queueing"? | Partially fair. Mitigation is the same four properties: bandits assume constant pull cost and free switching, both false here. **This must be demonstrated, not asserted** — Stage 2B died from asserting an analogous claim |
| 4 | Does an agent property materially change the problem? | Provisionally yes (escalating marginal cost + KV-state switching cost). **Currently PLAUSIBLE BUT UNVERIFIED — this is the first thing to measure** |
| 5 | Falsifiable? | Yes, sharply: if success-aware allocation does not beat age-aware and success-blind baselines on task goodput with non-overlapping CIs, the mechanism claim is dead |
| 6 | Can we collect the data? | Yes. Public benchmarks (Terminal-Bench, SWE-bench-verified) with open scaffolds (OpenHands, mini-SWE-agent), instrumented locally |
| 7 | Implementable without private traces? | Yes. 2608.00101's production traces are proprietary but are only needed for external-validity comparison, not for the result |
| 8 | Requires training large models? | No. Behaviour-only signals (tool error rate, edit churn, repetition, context growth) need no model access; activation probes need only open-weight small models |
| 9 | Evidence in 8–12 weeks? | The C2/C6 measurement half, yes. The C1 mechanism half is tight but feasible **only if trace collection starts immediately** |

---

## 5. Known execution risks

1. **No Python interpreter is installed on the development machine** (established Stage 1, still
   true). This blocks everything and must be fixed first.
2. **GPU access is unknown and unstated.** C1's strongest form needs open-weight serving; its
   minimum form needs only API-model trajectories plus a replay harness. **The direction must
   be scoped to the hardware actually available — this needs an answer before Stage 3.**
3. **Trace collection cost.** Running 500–1000 agent trajectories on frontier APIs has a real
   dollar cost that must be budgeted before committing.
4. **The field moves in weeks.** 2608.24087 appeared four days before this review; 2608.00101
   and 2608.04458 within the month. Any direction here has a shelf life measured in months, and
   a re-check is mandatory before writing.
