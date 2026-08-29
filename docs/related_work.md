# Related Work — Stage 2 Adversarial Literature Review

Status: **first literature pass complete.** Purpose was to find work that *invalidates*
novelty, not to defend ReSched.
Date of search: 2026-08-23. All searches performed via web search + direct fetch of
publisher/arXiv pages.

---

## 0. Verification status legend

Every row carries a verification level. **No citation in this file was written from
memory.**

| Level | Meaning |
|---|---|
| **V1** | Landing page (arXiv abs / proceedings page) fetched directly; title, authors, date, abstract read verbatim |
| **V2** | Full text or methodology section fetched and read beyond the abstract |
| **V3** | Existence and bibliographic data confirmed via publisher/index page (USENIX, ACM DL, PMLR, dblp) in search results, but page not fetched directly |
| **U** | **UNVERIFIED** — appeared in search results only; bibliographic details not confirmed. Must be verified before any use in a paper |

Open verification debts are listed in §8.

---

## 1. Search log

| Date | Source | Query theme | Screened | Kept |
|---|---|---|---|---|
| 2026-08-23 | Web + arXiv | SAGA / workflow-atomic agent scheduling | 8 | 1 |
| 2026-08-23 | Web + arXiv | Architectural implications of agentic AI | 9 | 1 |
| 2026-08-23 | Web + PMLR | INFERCEPT / augmented LLM inference | 9 | 1 |
| 2026-08-23 | Web + ICLR | Preble / distributed prompt scheduling | 10 | 1 |
| 2026-08-23 | Web | speculative execution + DAG + validation + rollback | 9 | 2 |
| 2026-08-23 | Web | stochastic scheduling with failure / rework / geometric retries | 7 | 3 |
| 2026-08-23 | Web + arXiv | pipelined filter ordering / cost-selectivity ratio | 6 | 2 |
| 2026-08-23 | Web + arXiv | speculative execution for LLM agents 2026 | 8 | 6 |
| 2026-08-23 | Web | Hopper / speculation-aware cluster scheduling | 9 | 1 |
| 2026-08-23 | Web + ACM DL | Time Warp / optimistic synchronization / rollback | 9 | 1 |
| 2026-08-23 | Web | reliability-aware workflow scheduling (cloud/grid) | 9 | 0 (area noted) |
| 2026-08-23 | Web | Helium / Agentix / AAFLOW | 24 | 3 |
| 2026-08-23 | Web | sequential testing / inspection ratio rule | 9 | 2 |
| 2026-08-23 | Web + arXiv | scheduling with testing / explorable uncertainty | 10 | 1 |
| 2026-08-23 | Web | conditional DAG / AND-OR precedence / recourse | 9 | 0 (area noted) |
| 2026-08-23 | Web | multi-tenant speculation under GPU contention | 7 | 2 |
| 2026-08-23 | Web + USENIX | Spark RDD lineage / Nectar incremental computation | 20 | 2 |
| 2026-08-23 | Web + ACM DL | transactional memory contention management | 9 | 1 |
| 2026-08-23 | Web | thread-level speculation resource allocation | 10 | 0 (area noted) |
| 2026-08-23 | Web | agentic failure/retry empirical characterization | 10 | 3 |

Areas searched that returned a large, mature literature but **no single work close
enough to enter the matrix** (recorded so the search is reproducible): reliability-aware
and replication-based workflow scheduling in cloud/grid; conditional/stochastic real-time
DAG scheduling; thread-level speculation resource allocation; MapReduce speculative-execution
heuristics beyond LATE/Mantri/Hopper.

---

## 2. Literature matrix — identification

| # | Work | Year | Venue / Status | Verif. |
|---|---|---|---|---|
| 1 | Sherlock: Reliable and Efficient Agentic Workflow Execution | 2025 | arXiv:2511.00330, preprint (cs.MA/cs.SE) | V2 |
| 2 | Parallelizing Tool Execution and LLM Generation for Low-Latency Agent Serving (PASTE) | 2026 | arXiv:2603.18897, preprint | V1 |
| 3 | SPORK: Self-Speculative Forking to Accelerate Agentic LLM Inference | 2026 | arXiv:2607.03333, preprint | V1 |
| 4 | Speculative Actions: A Lossless Framework for Faster Agentic Systems | 2025 | arXiv:2510.04371, preprint (OpenReview submission) | U |
| 5 | Cost-Aware Speculative Execution for LLM-Agent Workflows: An Integrated Five-Dimension Method | 2026 | arXiv:2606.07846, preprint | V1 |
| 6 | Dynamic Speculative Agent Planning (DSP) | 2025 | arXiv:2509.01920, preprint | V1 |
| 7 | Speculate with Memory: Lossless Acceleration for LLM Agents | 2026 | arXiv:2607.12236, preprint | V1 |
| 8 | SpecBox: Speculative Sandbox Scheduling for Efficient LLM Agent Serving | 2026 | arXiv:2607.23933, preprint | V1 |
| 9 | Hopper: Decentralized Speculation-aware Cluster Scheduling at Scale | 2015 | ACM SIGCOMM | V3 |
| 10 | Reining in the Outliers in Map-Reduce Clusters using Mantri | 2010 | USENIX OSDI | V3 |
| 11 | Improving MapReduce Performance in Heterogeneous Environments (LATE) | 2008 | USENIX OSDI | V3 |
| 12 | Virtual Time (Time Warp) — D. Jefferson | 1985 | ACM TOPLAS, doi:10.1145/3916.3988 | V3 |
| 13 | Adaptive Transaction Scheduling for Transactional Memory Systems — Yoo & Lee | 2008 | ACM SPAA, doi:10.1145/1378533.1378564 | V3 |
| 14 | Resilient Distributed Datasets (Spark) | 2012 | USENIX NSDI | V3 |
| 15 | Nectar: Automatic Management of Data and Computation in Datacenters | 2010 | USENIX OSDI | V3 |
| 16 | Adaptive Ordering of Pipelined Stream Filters — Babu et al. | 2004 | ACM SIGMOD, doi:10.1145/1007568.1007615 | V3 |
| 17 | Optimality of Sequential Filtering Under Independent Cost and Selectivity Models | 2026 | IEEE EIT 2026; arXiv:2606.07589 | V1 |
| 18 | Sequential testing of complex systems (review) — Ünlüyurt | 2004 | Discrete Applied Mathematics | **U** |
| 19 | An Adversarial Model for Scheduling with Testing — Dürr, Erlebach, Megow, Meißner | 2020 | Algorithmica 82(12):3630–3675; arXiv:1709.02592 | V3 |
| 20 | Autellix: An Efficient Serving Engine for LLM Agents as General Programs | 2025 | arXiv:2502.13965; **appears as "Agentix" at USENIX NSDI 2026** — naming unresolved, see §8 | V1 |
| 21 | SAGA: Workflow-Atomic Scheduling for AI Agent Inference on GPU Clusters | 2026 | arXiv:2605.00528, preprint | V1 |
| 22 | Efficient LLM Serving for Agentic Workflows: A Data Systems Perspective (Helium) | 2026 | arXiv:2603.16104, preprint (SIGMOD 2026 demo repo exists) | V1 |
| 23 | InferCept: Efficient Intercept Support for Augmented LLM Inference | 2024 | ICML (PMLR v235) | V3 |
| 24 | Preble: Efficient Distributed Prompt Scheduling for LLM Serving | 2025 | ICLR; arXiv:2407.00023 | V3 |
| 25 | Atomix: Timely, Transactional Tool Use for Reliable Agentic Workflows | 2026 | arXiv:2602.14849, preprint | V1 |
| 26 | Architectural Implications of Agentic AI Workflows | 2026 | arXiv:2608.04458, preprint | V1 |
| 27 | Agentic Coding in the Wild: Characterizing GitHub Copilot Traces at Production Scale | 2026 | arXiv:2608.00101, preprint | V1 |
| 28 | Agentic AI Workload Characteristics | 2026 | arXiv:2605.26297, preprint | V1 |
| 29 | AgentEval: DAG-Structured Step-Level Evaluation for Agentic Workflows | 2026 | ACL 2026 Industry Track (accepted); arXiv:2604.23581 | V1 |
| 30 | AAFLOW: Scalable Patterns for Agentic AI Workflows | 2026 | arXiv:2605.02162, preprint | U |

---

## 3. Literature matrix — problem and capability flags

Legend: **Y** = yes / central, **p** = partial or peripheral, **N** = no / not modelled,
**?** = could not determine from what was read.

| # | Work | Sched. unit | DAG | Stoch. runtime | Task failure | Retry-aware | Downstream invalidation | Speculative exec. | Validation / checkpoint | Recomputation | Resource heterogeneity | Objective | Core technique |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Sherlock | workflow node | Y | p | Y (semantic) | p | **Y** | **Y** | **Y** | **Y** | N (fixed 8×A100, no contention) | accuracy + latency | verifier placement + bounded speculation depth + rollback |
| 2 | PASTE | tool call + LLM session | p | p | N | N | N | **Y** | Y (LLM confirms) | p (discard) | p (tool CPU vs GPU) | task completion time | pattern-based tool prediction, isolation until confirm, joint tool/GPU scheduling |
| 3 | SPORK | LLM decode + tool call | N | p | N | N | N | **Y** | Y (confidence gate) | p (fallback to serial) | N | latency (P95) | self-forked probe predicts next tool |
| 4 | Speculative Actions | agent action | N | ? | N | N | N | **Y** | Y (commit on match) | p | ? | latency | small model predicts next action |
| 5 | Cost-Aware Spec. Exec. | workflow edge | Y | p | p | N | p | **Y** | Y (commit barrier) | Y (re-execution) | N | expected dollar cost vs latency | expected-value rule + Beta-Binomial posterior |
| 6 | DSP | agent plan step | p | ? | N | N | N | **Y** | Y | N | N | latency + dollar cost | online RL speculator |
| 7 | Speculate with Memory | agent step | N | N | N | N | N | **Y** | Y | N | N | prediction accuracy | memory-augmented speculator; **explicitly assumes idle resources** |
| 8 | SpecBox | tool sandbox | p | p | N | N | N | **Y** (prewarm) | N | N | p (CPU sandbox, memory) | P99 latency, memory | intent-driven prewarm + stochastic prefetch |
| 9 | Hopper | task + speculative copy | Y | **Y** | p (stragglers) | p | N | **Y** (duplicate) | N | p | p | job completion time | speculation-aware slot allocation under capacity |
| 10 | Mantri | task | Y | Y | Y (outliers) | Y | p | Y | N | Y | p | job completion time | cause-aware restart/duplicate + output protection |
| 11 | LATE | task | Y | Y | p | N | N | Y | N | N | Y (heterog. nodes) | response time | back up task with longest est. time to end |
| 12 | Time Warp | logical process event | Y (causal) | N | N | N | **Y** | **Y** (optimistic) | **Y** (causality) | **Y** (rollback) | N | simulation throughput | optimistic execution + antimessages + GVT |
| 13 | Adaptive Txn Scheduling | transaction | N | N | N | p (abort) | p | **Y** | **Y** (conflict) | **Y** | N | throughput | throttle speculative concurrency by contention feedback |
| 14 | Spark RDD | partition/stage | Y | N | Y (node loss) | Y | p | N | N | **Y** (lineage) | N | fault-tolerant throughput | lineage-based recomputation |
| 15 | Nectar | sub-expression | Y | N | N | N | N | N | N | Y (reuse) | N | cluster efficiency | cache + rewrite of intermediate results |
| 16 | Pipelined filter ordering | filter stage | p (chain) | N | N (rejection) | N | N | N | Y (filter = test) | N | N | expected cost | adaptive greedy ordering by cost/selectivity |
| 17 | Optimality of Seq. Filtering | filter stage | N | N | N (rejection) | N | N | N | Y | N | N | expected cost | proves cost/rejection-prob. ratio ordering optimal |
| 18 | Ünlüyurt (sequential testing) | component test | p | N | N | N | N | N | **Y** | N | N | expected inspection cost | cost-to-probability ratio; NP-hard w/ general precedence |
| 19 | Scheduling with Testing | job + optional test | N | **Y** | N | N | N | N | **Y** (test reveals) | N | N | competitive ratio | explorable uncertainty, adversarial model |
| 20 | Autellix / Agentix | LLM call, program-aware | Y (dynamic) | p | N | N | N | N | N | N | p | program end-to-end latency | PLAS/ATLAS attained-service preemption |
| 21 | SAGA | whole agent workflow | Y | p | N | N | N | N | N | N | p | task completion time, fairness | agent execution graphs, KV-reuse-aware placement |
| 22 | Helium | LLM call as operator | Y (query plan) | N | N | N | N | p ("speculative exploration" as redundancy) | N | p (reuse) | N | speedup via reuse | templated radix tree, cache-aware ordering |
| 23 | InferCept | request w/ interception | N | p | N | N | N | N | N | p (recompute KV) | N | throughput | KV discard/preserve/swap policy |
| 24 | Preble | request/prompt prefix | N | p | N | N | N | N | N | p | Y (multi-GPU) | latency (avg, p99) | prefix-aware distributed scheduling |
| 25 | Atomix | tool effect / transaction | p | N | Y (effects) | Y | **Y** | p (isolates spec. work) | **Y** (commit frontier) | p (compensation) | N | correctness/atomicity | transactional runtime, effect frontiers |
| 26 | Arch. Implications | — (characterization) | — | Y (measured) | ? | ? | N | N | N | N | **Y** (CPU/GPU) | characterization | Azure production + open-source study |
| 27 | Agentic Coding in the Wild | — (characterization) | — | Y (measured) | Y (tool failures) | Y (retries) | N | N | N | N | p | characterization | 13M-session Copilot trace study |
| 28 | Agentic AI Workload Char. | — (characterization) | — | Y | ? | ? | N | N | N | N | p | characterization | end-to-end ReAct tracing |
| 29 | AgentEval | workflow step | Y | N | Y (semantic) | p (retry loops) | Y (error propagation) | N | Y (step-level eval) | N | N | eval recall / root cause | DAG-structured step evaluation |
| 30 | AAFLOW | operator | Y | N | N | N | N | N | N | N | p | communication efficiency | Arrow/Cylon zero-copy data plane |

### Relation to the candidate ReSched problem (per work)

- **1 Sherlock** — *Direct hit on the reformulation.* Same mechanism (speculate past an unvalidated node, verify in background, roll back on failure) in the same domain. Differs only in that it is single-workflow, accuracy-oriented, and contention-free.
- **2, 3, 4, 6, 7, 8** — Speculative agent execution as **latency hiding during idle time**. All assume the resource used for speculation is otherwise idle. #7 states this explicitly ("lossless because it runs during idle time at zero added wall-clock cost").
- **5** — Closest formal decision rule: expected-value speculation with a failure-weighted cost term. Prices speculation in dollars, not in contended capacity. Single-author preprint; self-describes as a combination of existing ideas.
- **9, 10, 11** — Speculation as a **cluster scheduling** problem under capacity. #9 is the direct structural precedent: it proves that speculation and scheduling must be co-designed because a speculative copy consumes resources other jobs need.
- **12, 13** — The canonical optimistic-execution-with-rollback formalisms. #13 is the precedent for *throttling* speculation under contention.
- **14, 15** — Recomputation/lineage; establishes the accounting of "work that must be redone," not the scheduling of it.
- **16, 17, 18, 19** — The theory of ordering uncertain/verifying steps. See Special Test 1.
- **20, 21, 22, 23, 24, 30** — Agent/LLM serving schedulers. **None of them model failure, verification, or invalidation at all.** They are the "workflow-aware but failure-oblivious" class our Stage 1 baselines were gesturing at, and they are far stronger than the placeholder baselines we had written down.
- **25** — Correctness/atomicity runtime for agent tool effects, including isolation of speculative work. Adjacent but not a scheduler.
- **26, 27, 28, 29** — Evidence sources for workload realism (Special Test 3).

---

## 4. SPECIAL TEST 1 — Retry-adjusted expected work

**Question:** is `E[work] = r/(1-p)` under geometric retry, and ordering by a
cost-to-failure-probability ratio, already standard?

**Answer: yes. This is classical and cannot be a contribution.**

Evidence:

- **Sequential testing (Ünlüyurt review, U — must verify):** for a serial system without
  precedence constraints, *every* sequence that inspects components in non-decreasing
  order of the **cost-to-failure-probability ratio** is optimal; the result generalizes to
  polynomial algorithms under series-parallel precedence and is NP-hard for general
  precedence. This is the exact structure of "order risky verification steps."
- **Pipelined filter ordering (Babu et al., SIGMOD 2004, V3):** the adaptive-greedy
  ordering of filters by cost/selectivity, with convergence guarantees and handling of
  correlated selectivities.
- **Optimality of Sequential Filtering (arXiv:2606.07589 / EIT 2026, V1):** re-proves in
  2026 that "ordering filters by increasing ratio of cost to rejection probability
  minimizes expected total cost." Notably, this paper presents the rule as requiring
  fresh proof and **does not cite the classical ratio-rule literature** — evidence that the
  result is repeatedly rediscovered, which is precisely the trap we were heading into.
- **Rework/unreliable-machine scheduling (OR literature, U):** stochastic scheduling with
  rework, reprocessing, and machine failure, including geometric cycle-time models, is a
  mature subfield; "Total Estimated Processing Time" combining processing + rework +
  reprocessing time is an existing construct.

**Consequence.** Strategy **C** from the audit (inflate estimates by `r/(1-p)` and run a
conventional scheduler) is a textbook application, not a research contribution. It must be
implemented as a **baseline**, and a strong one. Strategy **A** (run risky/cheap-to-check
work first) is the classical ratio rule and is likewise a baseline, not a contribution.

---

## 5. SPECIAL TEST 2 — Speculation vs. validation

**Question:** is the formulation "A produces a tentative result; B executes before
validator V finishes; V can invalidate A; B is discarded and recomputed" already studied?

**A. Is the scheduling problem already formally studied? — Yes, in three separate literatures.**

1. **Optimistic parallel execution.** Time Warp / Virtual Time (Jefferson, TOPLAS 1985)
   is exactly this structure: processes advance speculatively on unvalidated state and roll
   back via antimessages when a causality violation is detected. Rollback cascades to
   descendants. This is a 40-year-old formalism.
2. **Speculation-aware cluster scheduling.** Hopper (SIGCOMM 2015) is the direct
   precedent for the *resource* half: it shows speculation must be co-designed with
   scheduling because speculative work consumes capacity other jobs need, and allocates
   speculation slots as a function of job size and cluster load.
3. **Speculation throttling under contention.** Yoo & Lee (SPAA 2008) throttle the number
   of concurrently executing speculative transactions based on contention feedback,
   explicitly to avoid wasted work when parallelism is insufficient.

**And — decisively — it is already studied in the agent setting.** Sherlock
(arXiv:2511.00330) speculatively executes downstream workflow nodes while verification runs
in the background, rolls back to the last verified output on verification failure, chooses
where to place verifiers, and uses an explicit expected-cost model
`C_spec = (1 − m_i) · Σ (C_exec + C_vrf)` over the speculated node set. That is the
candidate reformulation, in the candidate domain, published nine months ago.

**B. What assumptions differ from a contended agent setting?**

| Assumption | Time Warp / TM | Hopper / Mantri / LATE | Sherlock & agent-speculation cluster |
|---|---|---|---|
| What speculative work is | same logical computation, wrong time | **duplicate of the same task** | different work on an unvalidated artifact |
| Why it becomes invalid | causal order violation / data conflict | never (duplicate is always valid) | **semantic verifier rejects the artifact** |
| Invalidation scope | cascade to descendants | none | sub-DAG of descendants |
| Resource model | cores, µs granularity | cluster slots, contended | **dedicated cluster, contention not modelled** |
| Concurrency | many processes | many jobs, multi-tenant | **one workflow at a time** |
| Cost measured | rollback overhead | slot-seconds | tokens / dollars; **GPU utilization and idle capacity not measured** |

**C. Would applying the same scheduler to agents be merely an application paper? — For the
reformulation as literally stated in the prompt, yes.** "Speculative execution under late
validation for agentic workflows" is occupied by Sherlock and, in weaker forms, by six other
2025–2026 preprints. Re-deriving it in a simulator would be a reproduction, not a contribution.

**D. Is there an agent-specific property that changes the problem substantially?**

One candidate survives scrutiny, and only one:

> In every agent-speculation paper found, speculation is treated as **free** because it runs
> in resource that is assumed idle. Under multi-tenant contention for scarce GPU capacity,
> speculation is not free — it is a **resource allocation decision with an externality on
> other tenants**, and unvalidated work that is later invalidated is capacity that a
> validated request could have used.

This is exactly the transition Hopper made for straggler speculation in 2015 (from
"speculate when a task looks slow" to "speculate only when the cluster can afford it"), and
it has not been made for validation-driven agent speculation. Sherlock evaluates on a
dedicated 8×A100 with no competing workflows and does not report GPU utilization or idle
cycles; "Speculate with Memory" defines its speculation as lossless *by assuming* idle time.

That is a real, narrow, defensible gap. It is also a **composition of two known ideas**, and
a reviewer can reasonably describe it as "Hopper's question asked about Sherlock's mechanism."

---

## 6. SPECIAL TEST 3 — Agent-specific justification, with evidence grading

| Claimed characteristic | Status | Evidence |
|---|---|---|
| Workflows repeatedly cross the CPU–GPU boundary; CPU on the critical path | **MEASURED** | Architectural Implications (#26), Azure production study |
| Load is low with sudden spikes (burstiness); tool spikes threaten tail latency | **MEASURED** | #26 |
| Model composition determines how evenly GPUs are used; task/tool diversity widens the range | **MEASURED** | #26 |
| Tool-call failures and retries occur at production scale; repeated failures trap agents in recovery loops that consume turns without progress | **MEASURED** | Agentic Coding in the Wild (#27), 3.2M users / 13M sessions / 761M LLM calls, June 2026 Copilot traces |
| KV cache hit rate ~90% within a turn, ~55% across turn boundaries; minutes-long user idle at turn boundaries | **MEASURED** | #27 (exact figures from abstract) |
| Agentic execution is decode-dominated with long-lived KV state; tool use shifts read/explore → execute/write over a session | **MEASURED** | Agentic AI Workload Characteristics (#28) |
| ~12% of agentic traces do not conform to strict DAGs (retry loops, dynamic branching); intermediate failures dominate real error budgets | **MEASURED** (12% figure verified; the retry-8%/branch-4% split appeared in search text but **not** in the fetched page — treat as **U**) | AgentEval (#29) |
| Chained LLM calls per task in the tens-to-hundreds; idle wait is 16–37% of wall time | **MEASURED, single-source** | SAGA (#21) for call counts; SPORK (#3) for idle fraction — both preprints, not peer reviewed |
| Semantic verification steps are a distinct workload component with their own cost | **PLAUSIBLE BUT UNVERIFIED as a production property** | Sherlock (#1) constructs verifiers; no production measurement found |
| Failure probability is predictable from task type / context | **PLAUSIBLE BUT UNVERIFIED** | No study found that measures the predictability of agent step failure in production |
| Failures are correlated within a workflow (a hard instance fails everywhere) | **PLAUSIBLE BUT UNVERIFIED** | Recovery-loop evidence in #27 is suggestive, not a measurement of correlation |
| Retry attempts are non-i.i.d. (error feedback improves success) | **UNVERIFIED** | No source found |

**Assessment.** Agent workloads *do* have measured distinctive properties — CPU/GPU
interleaving, burstiness, real tool-failure and retry-loop behaviour, long-lived KV state.
But the two properties our method most depends on — **that failure probability is
predictable**, and **that retries are non-i.i.d.** — have no measured support in anything
found. Those would have to be established, not assumed.

---

## 7. Closest-competitor analysis

### The ten closest prior works, ranked by threat

1. **Sherlock** (#1) — the reformulation, already done, in-domain.
2. **Hopper** (#9) — the resource-contention question, already answered for duplicate speculation.
3. **Cost-Aware Speculative Execution** (#5) — the expected-value speculation rule with invalidation cost.
4. **PASTE** (#2) — speculative tool execution *with* joint tool/GPU scheduling.
5. **Time Warp** (#12) — the underlying formalism, 1985.
6. **Adaptive Transaction Scheduling** (#13) — speculation throttling under contention.
7. **Ünlüyurt / pipelined filter ordering** (#18, #16) — the ordering theory that subsumes strategies A and C.
8. **Speculative Actions / SPORK / DSP / Speculate-with-Memory** (#4, #3, #6, #7) — the crowded agent-speculation field.
9. **Autellix/Agentix, SAGA, Helium** (#20, #21, #22) — the agent-workflow scheduling baselines we must beat.
10. **Atomix** (#25) — the correctness constraints that bound which speculation is even admissible.

---

### 7.1 Sherlock: Reliable and Efficient Agentic Workflow Execution (arXiv:2511.00330, V2)

1. **Problem.** Errors at one workflow step propagate and amplify downstream; verification
   is expensive, so where should verifiers go and how much may be speculated past them?
2. **System/model.** Agentic workflow as a DAG of LLM/tool nodes; verifiers (self-refine,
   debate, LLM-as-judge) attachable per node; evaluated on 8×A100.
3. **Scheduling decision.** Three: verifier *placement* (which nodes), verifier *selection*
   (which algorithm), and *speculation depth* (how far downstream to run while verification
   is in flight).
4. **Failure/speculation semantics.** Match rate `m_i` = probability the verifier agrees
   with the original output. Expected speculative cost
   `C_spec^i = (1 − m_i) · Σ_{j∈N_spec} (C_exec^j + C_vrf^j)`. On failure, dependent nodes
   are reverted and re-executed. Speculation proceeds only if downstream latency fits inside
   the verifier's latency window.
5. **Evaluation.** Baselines: random/even placement, static single verifier, tabular
   lookup, AFlow (Monte Carlo search), and an oracle. Metrics: accuracy, time-to-end
   execution, time-to-end verification, verification cost in GPU-hours and tokens.
   Reported: +18.3% accuracy, up to −48.7% latency vs. non-speculative, −26.0% verification cost.
6. **Overlap with our candidate idea.** Essentially total on mechanism: speculate past an
   unvalidated node, verify concurrently, roll back and recompute the invalidated sub-DAG,
   and decide how much to speculate using an expected-cost model that includes the
   probability of invalidation. Our proposed "novel mechanism" is their existing mechanism.
7. **What differs.** (a) It optimizes **accuracy and per-workflow latency**, not cluster
   efficiency. (b) It runs **one workflow at a time** on a dedicated cluster — no competing
   tenants, no queueing, no admission decision. (c) It costs speculation in **tokens and
   GPU-hours of the workflow itself**, and does not measure GPU utilization, idle cycles, or
   capacity denied to other work. (d) Verifier *placement* is its central decision; ours
   would be *whether to spend contended capacity* on speculation at all.
8. **Is the difference scientifically substantive?** Partially. Moving from a
   single-workflow latency/accuracy objective to a multi-tenant capacity-allocation objective
   is a genuine change of problem — the optimal speculation depth becomes a function of
   system load and of other tenants' marginal value, which does not appear in Sherlock's
   model at all. But it is a change of *setting*, not of *mechanism*.
9. **Could a reviewer say "this is just X applied to AI agents"?** They would say something
   sharper: *"this is Sherlock evaluated under load."* That criticism is fair unless the
   multi-tenant formulation produces a qualitatively different policy — e.g. a demonstrated
   load threshold above which Sherlock's own rule becomes harmful.

### 7.2 Hopper: Decentralized Speculation-aware Cluster Scheduling at Scale (SIGCOMM 2015, V3)

1. **Problem.** Stragglers are mitigated by speculative copies, but speculation mechanisms
   are designed independently of the job scheduler, even though a speculative copy consumes
   slots other jobs need.
2. **System/model.** Cluster of slots; jobs of many tasks; centralized and decentralized
   prototypes.
3. **Scheduling decision.** How many slots to grant each job for speculative copies, as a
   function of job size and how busy the cluster is.
4. **Failure/speculation semantics.** Speculation = **duplicate execution of the same
   task**. There is no validation step and no semantic invalidation: the duplicate is always
   a valid result, and the benefit is `min` of two completion times.
5. **Evaluation.** ~50% improvement over centralized and ~66% over decentralized
   state-of-the-art schedulers with their own speculation strategies.
6. **Overlap.** The *question* is ours: speculation must be rationed against the
   opportunity cost of contended capacity, and the right amount depends on load.
7. **What differs.** No dependency cascade (a duplicate cannot invalidate descendants), no
   verifier, no probability-of-being-wrong, homogeneous slots rather than CPU/GPU classes,
   and failure is *stochastic straggling* rather than *semantic rejection*.
8. **Substantive?** Yes, the cascade changes the mathematics: in Hopper the downside of
   speculating is bounded by the slot-seconds consumed; with validation cascades, the
   downside is the entire speculatively-built sub-DAG, which grows with how far ahead you
   ran. That is a genuinely different cost structure.
9. **Reviewer's line.** *"Hopper already told us to make speculation scheduling-aware; you
   changed what gets invalidated."* We would need the cascade to demonstrably change the
   optimal policy, not merely the constant.

### 7.3 Cost-Aware Speculative Execution for LLM-Agent Workflows (arXiv:2606.07846, V1)

1. **Problem.** Whether to launch a downstream agent operation on a predicted upstream
   input, when each speculation costs real money and its success probability drifts.
2. **System/model.** Workflow edges annotated with an admissibility precondition
   (side-effect-free, idempotent, or stageable behind a commit barrier).
3. **Scheduling decision.** Per-edge fire/don't-fire, via an expected-value rule with a
   failure-weighted cost term and a preference-adjusted threshold.
4. **Semantics.** A wrong speculation is rolled back by re-execution, which "refunds tokens
   but cannot un-send an irreversible side effect."
5. **Evaluation.** Synthetic validation suite plus contrast tables against DSP, Speculative
   Actions v2, Sherlock, and B-PASTE. **No real deployment results.**
6. **Overlap.** The decision rule is structurally what a "ReSched" priority would be:
   expected value of speculating, weighted by failure probability and re-execution cost.
7. **What differs.** Prices speculation in **dollars per token**, not in contended
   capacity; no queueing, no other tenants, no GPU model. Single-author preprint that itself
   admits "variants of these ideas appear in recent work."
8. **Substantive?** The paper is weak (synthetic-only, self-described as a combination),
   but it establishes **prior disclosure** of the expected-value speculation rule with a
   failure-weighted invalidation term. Even a weak preprint blocks that specific claim.
9. **Reviewer's line.** *"Your decision rule is equation (4) of arXiv:2606.07846 with
   GPU-seconds substituted for dollars."*

### 7.4 PASTE (arXiv:2603.18897, V1)

1. **Problem.** Tool latency sits exposed on the agent critical path because serving
   systems serialize the generate→tool loop.
2. **System/model.** Tool-aware agent-serving system; speculative tool execution during LLM
   generation; deep-research, coding, and scientific-agent workloads.
3. **Scheduling decision.** Which tool calls to launch speculatively, **and** joint
   scheduling of tool execution against returning LLM sessions "to avoid shifting bottlenecks
   to the GPU."
4. **Semantics.** Speculative results are isolated until confirmed by the LLM; unconfirmed
   work is discarded.
5. **Evaluation.** −43.5% average task completion time, 1.8× lower observed tool latency.
6. **Overlap.** This is the closest work to the *contention* angle: it explicitly notices
   that speculation can shift the bottleneck onto the GPU and schedules to avoid it.
7. **What differs.** Speculation is over *tool calls* (mostly CPU/external), the validator
   is the LLM's own subsequent generation rather than a semantic verifier, and there is no
   cascade of invalidated descendants.
8. **Substantive?** This is the most dangerous partial overlap for the multi-tenant angle,
   because "don't let speculation shift the bottleneck" is a version of our proposed
   contribution. **Its full text must be read before any design is finalized** — the abstract
   alone cannot tell us how deeply it models contention.
9. **Reviewer's line.** *"PASTE already jointly schedules speculative tool work and GPU
   sessions."*

### 7.5 Time Warp / Virtual Time (Jefferson, TOPLAS 1985, V3)

1. **Problem.** Synchronizing distributed computation without conservative blocking.
2. **System/model.** Logical processes with virtual timestamps; global virtual time for
   commit.
3. **Decision.** Execute optimistically; never block on the possibility of a later-arriving
   causal predecessor.
4. **Semantics.** On a causality violation, roll back to a prior state and cancel
   downstream effects via antimessages — a **cascading invalidation of speculative
   descendants**, which is precisely our proposed mechanism, expressed in 1985.
5. **Evaluation.** Parallel discrete-event simulation throughput.
6. **Overlap.** The invalidation-cascade semantics are identical in structure.
7. **What differs.** Invalidation is triggered by *causal order*, which is deterministic
   and detectable, not by a *probabilistic semantic verdict*; there is no notion of
   "probability this result is valid," hence no expected-value scheduling decision; and the
   resource is CPU cores at microsecond granularity, not GPU-seconds.
8. **Substantive?** Yes — the probabilistic verdict is what makes a *scheduling* decision
   exist at all (Time Warp always speculates). But it means we cannot claim the mechanism as
   new, only the decision problem layered on it.
9. **Reviewer's line.** *"This is optimistic execution with a rollback cost model; see also
   the entire PDES literature on optimistic vs. conservative synchronization and throttling."*

---

## 8. Open verification debts (must close before any paper draft)

1. **Ünlüyurt 2004** (#18) — cited from search text only. Obtain the Discrete Applied
   Mathematics article and confirm the ratio-rule statement and precedence-constraint results.
2. **Autellix vs. Agentix** (#20) — the NSDI 2026 page returned HTTP 403. Confirm whether
   these are the same work renamed, and cite the correct camera-ready title/venue.
3. **PASTE** (#2) — the arXiv abs page returned title *"Parallelizing Tool Execution and LLM
   Generation for Low-Latency Agent Serving"*, while search results listed *"Act While
   Thinking: Accelerating LLM Agents via Pattern-Aware Speculative Tool Execution"* for the
   same ID. Version rename suspected. Read the **full text** and fix the citation.
4. **Speculative Actions** (#4) and **AAFLOW** (#30) — not fetched; verify.
5. **Sherlock** (#1) — read the full evaluation section directly rather than via extraction,
   to confirm the "no multi-workflow contention" claim, which our entire gap depends on.
6. **Hopper** (#9), **Mantri** (#10), **LATE** (#11), **Spark** (#14), **Nectar** (#15),
   **Yoo & Lee** (#13), **Babu et al.** (#16), **Jefferson** (#12) — bibliographic data
   confirmed via publisher/index pages; read the papers before characterizing them in prose.
7. **AgentEval retry-loop split** (8% retry / 4% branching) — appeared in search text, not in
   the fetched page. Verify or drop.
8. **SAGA** (#21) and **AgentEval** (#29) share an author set (Guo, Wu, Yiu); SAGA is an
   unrefereed preprint. Do not treat its workload claims as independently established.

---

## 9. Assumptions this review supports or refuses to support

| Stage 1 assumption | Verdict after literature pass |
|---|---|
| Retry rates in agent workflows are non-trivial | **Supported** (#27, production traces) |
| Failure probability is predictable from task type | **Not supported by any measurement found** |
| Retries are i.i.d. across attempts | **Not supported; no source either way** |
| Lognormal runtimes (A4) | **Not supported by any agent measurement found** |
| CPU and GPU both matter and interleave | **Supported** (#26) |
| Local-retry-only default is a reasonable v1 | **Refuted as a research design** — the entire live literature is about invalidation cascades, which local-retry excludes |
| Baselines FIFO/SJF/CPF are adequate | **Refuted** — real baselines are Autellix/Agentix, SAGA, Sherlock, Hopper-style speculation control, and ratio-rule ordering |

---

# Stage 2B Full-Text Kill Test

Date: 2026-08-23. Purpose: resolve the two blocking prior-art questions from full text,
plus a classical-equivalence search, and apply a pre-committed kill test to the candidate
gap. **Outcome: the candidate gap did not survive.** Evidence below.

## 2B.1 Sherlock (arXiv:2511.00330) — full text

Fetched: HTML full text (system + evaluation) and PDF. **The PDF extraction returned
generic paraphrase and is not trustworthy; only the HTML-derived findings are used.**

| Question | Finding |
|---|---|
| Resource model | Static model-to-GPU assignment. 8×NVIDIA A100 80GB. Llama-3.1-8B-Instruct executor on 2 GPUs; Llama-3.3-70B-Instruct Advanced-Refine verifier on 4 GPUs; Qwen2.5-7B-Instruct secondary executor on 1 GPU; Selene-1-Mini-Llama-3.1-8B judge on 1 GPU. Served with vLLM. |
| Concurrency | **One workflow at a time.** No statement of concurrent workflow count anywhere. |
| Multi-tenancy | **None.** |
| Contention between workflows | **Not modelled.** |
| Global scheduler across competing workflows | **None.** |
| GPU capacity / queues / batching / KV contention / utilization | **None modelled or measured.** No sentence in the paper discusses contention, utilization, throughput, or queueing. |
| Arrival process / offered load / queueing model | **Absent.** |
| Throughput or GPU-utilization measurements | **Absent.** Cost is reported in GPU-hours and tokens of the workflow itself. |
| Where speculative work runs | On the same statically-assigned executor GPUs, concurrently with the verifier: *"Once node W1 completes, Sherlock immediately launches its verifier in the background while concurrently executing child nodes (W2, W3)."* |
| Is spare capacity assumed? | **Yes, implicitly.** Never quantified or constrained. |
| Externality on other users in the cost function | **Absent.** |

**Sherlock's decision rule (equation numbers as in the paper):**

- **Eq. 4** — speculation-eligible set bounded by the verifier latency window:
  `N_spec = { j | Σ_{k=i..j} lat_exec(k) < lat_vrf(i) }`
- **Eq. 5** — budget constraint: `C_spec(d) ≤ B`
- **Eq. 6** — expected speculative cost:
  `C_spec^i = (1 − m_i) · Σ_{j ∈ N_spec} (C_exec^j + C_vrf^j)`
- **Eq. 7/8** — refinement of `N_spec` for parallel execution across depth levels:
  `N_spec = { j | Σ_{l=1..depth(j)} max_{k ∈ D_l} lat_exec(k) < lat_vrf(i) }`

Symbols: `i` = node whose output is being verified; `m_i` = **match rate**, the probability
the verifier agrees with the executor's output at node `i`; `N_spec` = set of downstream
nodes executed speculatively while verification of `i` is pending; `C_exec^j`, `C_vrf^j` =
execution and verification cost of node `j`; `lat_exec`, `lat_vrf` = execution and verifier
latency; `D_l` = nodes at depth level `l`; `B` = user-specified cost budget; `d` =
speculation depth. Verifier placement uses **Algorithm 1, a greedy topology-driven
heuristic** (terminal nodes, then initial nodes, then intermediates by fan-in), not DP or search.

**Could Sherlock's policy be deployed unchanged in a saturated multi-tenant system?**
No. Three things are missing: (a) `lat_exec` and `lat_vrf` are treated as fixed properties,
but under load they are queue-dependent, so `N_spec` (Eq. 4/8) is computed from latencies
that speculation itself inflates; (b) the budget `B` is per-workflow and exogenous — there
is no mechanism to shrink it when the cluster is busy; (c) `C_spec` counts only the
speculating workflow's own tokens/GPU-hours, so the capacity denied to other tenants is
invisible to the objective.

**Reviewer challenge: "Your paper is just Sherlock evaluated under load."**

- *Strongest argument FOR the criticism:* the mechanism is unchanged. Eq. 6 already prices
  cascading invalidation with a probability term; adding a queueing term is the kind of
  extension a competent engineer makes in a week. The paper's authors would likely regard
  contention as an implementation detail they abstracted, not a research question they missed.
- *Strongest argument AGAINST:* under contention `lat_exec`/`lat_vrf` become endogenous to
  the speculation decision, so Eq. 4's window is no longer a constant — the eligible set
  depends on the allocation, and the allocation depends on the eligible set. That is a fixed
  point, not a substitution, and it can invert the policy (speculating deeper shrinks the
  window that justified speculating deeper).
- *Assessment:* the FOR argument is stronger. The fixed-point observation is real but is a
  refinement of an existing rule, not a new problem.

## 2B.2 PASTE (arXiv:2603.18897) — full text

**Consistency warning.** Two fetches of the same arXiv ID returned *materially different*
scheduling formulations — one reporting a knapsack-style program
`max Σ x_j p_j T_j s.t. Σ x_j c_j ≤ min(R_slack, B)`, the other reporting
`priority(i) = ExposedToolGain(i) / LLMPressure(i, load) + Aging(i)` and stating that no
formal optimization problem is given. This is likely a version difference (v1 vs. later) or
extraction error. **Both are recorded; neither is treated as settled.** The findings below
are limited to what *both* extractions agree on.

| Question | Finding (agreed across both extractions) |
|---|---|
| What is speculated | Future tool invocations with concrete arguments, predicted from recurring agent patterns |
| Job classes | **Authoritative** (agent-issued, correctness-critical) vs. **speculative** (predicted, best-effort) |
| Concurrency / multi-tenancy | **Yes** — multi-session concurrent agent requests, sweeping arrival rate and concurrent sessions |
| Arrival process | **Yes** — replayed production Azure Functions invocation trace, bursty arrivals at logged timestamps |
| Hardware | 4 nodes × 8 A100-80G (32 GPUs), 96 vCPU + 512 GB per node |
| Does speculation consume capacity others could use? | **Yes, and the paper says so:** speculative jobs *"run only within bounded or opportunistic capacity, are lower priority, and can be suppressed or preempted when authoritative work needs resources."* |
| How is that capacity rationed? | Slack/opportunistic budget with priority demotion and preemption. *"This resource rule keeps speculative execution from delaying correctness-critical tool work across concurrent sessions."* |
| Does the priority price interference on others? | **Yes** — `LLMPressure(i, load)` explicitly includes predicted LLM service time, queue/batch pressure, context length, and KV/cache pressure |
| Semantic validation failure model | **No.** Validation is "the LLM's subsequent generation matched or did not match." Mispredictions simply waste bounded resources |
| Sub-DAG invalidation / cascade | **No.** No cascading invalidation of descendants; no blast-radius model |
| Failure probability / expected invalidated work | Uses a pattern-confidence `p` for *prediction accuracy*; **does not** estimate downstream work invalidated by a wrong speculation |
| Objective | Primarily per-workflow task completion time (−48.5%), secondarily tool throughput (1.8×) |
| Safety | Policy-constrained graded speculation; 602 of 20,000 speculative actions blocked as side-effecting |

**Reviewer challenge: "This is PASTE plus a verifier."**

- *Strongest argument FOR:* PASTE already owns the entire contention half of the candidate
  gap — two job classes, slack budgeting, preemption of speculative work under pressure, an
  interference-aware priority term, a real bursty arrival trace, and 32 GPUs. Adding a
  verifier and swapping the per-item waste `c_j` for Sherlock's `(1−m)·Σ(C_exec+C_vrf)` is a
  substitution into an existing scheduler.
- *Strongest argument AGAINST:* PASTE's speculative unit is *self-contained* — a wrong
  prediction wastes exactly one tool call, so its budget can be a fixed cap. With
  validation cascades the exposed quantity **grows monotonically while the validator runs**,
  so a static slack budget is the wrong control variable: the correct control is a *rate* of
  exposure accumulation, not a *cap* on concurrent speculative jobs.
- *Assessment:* the AGAINST argument identifies a genuine structural difference, but it is a
  refinement of PASTE's budget mechanism, and see §2B.4 — that exact refinement is the
  subject of a 30-year-old literature.

## 2B.3 Other close systems — the A-vs-B allocation test

Test: does the work contain a resource-allocation decision of the form
*validated work from workflow A* **vs.** *speculative/unvalidated work from workflow B*
under shared capacity, **and** does it price `P(invalidation) × exposed descendant work`
together with contention, queueing externality, and heterogeneous resources?

| Work | A-vs-B allocation under shared capacity | `P(inval) × exposed descendant work` | Combines both |
|---|---|---|---|
| **Sherlock** | **No** — single workflow, no contention | **Yes** — Eq. 6, the only exact match found | **No** |
| **PASTE** | **Yes** — authoritative vs. speculative across concurrent sessions, with interference-priced priority | **No** — per-item waste only, no cascade | **No** |
| **Cost-Aware Spec. Exec.** | **No** — explicitly excluded | **No** — single operation only | **No**, and it says so |
| **Hopper** | **Yes** — speculative copies rationed against other jobs' work by cluster load | **No** — a duplicate can never invalidate anything | **No** |
| **Atomix** | **No** — pure correctness/isolation runtime; explicitly delegates speculation choice to the orchestrator; no GPU/capacity model, no invalidation probability | **No** | **No** |
| **Autellix/Agentix** | Contention yes (Poisson arrivals, MLFQ across programs), speculation **no** — listed as *future work* | **No** | **No** |
| **SAGA** | Multi-tenant contention yes; speculation limited to **cache prefetching**, accuracy and waste unquantified | **No** — assumes all inference steps succeed | **No** |
| **Helium** | **No** failure/validation model | **No** | **No** |

**Cost-Aware Speculative Execution is the decisive entry.** Its rule (§6.1) is
`EV = P · L_value − (1 − P) · C_spec`, `speculate iff EV ≥ (1 − α) · C_spec`, where
`C_spec` covers **only the single speculated operation** — §6.2 states the failed
speculation "must be re-executed with the correct input," with no descendant cascade. More
importantly, **§14.2 explicitly names the contended-capacity case as out of scope and
identifies the fix:** it notes that under a fixed serving budget an aggressive `α`
"can raise tail latency for the rest of the workload," states that "this paper specifies only
the elastic-API case," and credits *B-PASTE's interference term (µ·ΔI)* as the "right hook
for the contended-capacity regime," left unimplemented.

**Consequence:** the candidate gap is not an unnoticed hole. It is a **signposted next step
already named in the literature**, with the mechanism identified.

## 2B.4 Classical / mathematical equivalence

Three formulations were examined. The first is the damaging one.

### (a) Optimism control in optimistic parallel discrete-event simulation

- **Entities:** logical processes (jobs) executing timestamped events (tasks) under a causal
  precedence order; speculative execution ahead of global virtual time (GVT).
- **Uncertainty:** whether a straggler message will arrive and invalidate already-executed
  events.
- **Invalidation:** rollback **cascades to all descendants** via antimessages — a
  speculatively-built sub-DAG is discarded exactly as in our formulation.
- **Resource constraint:** finite processors and finite memory for saved state.
- **Decision:** *how far ahead may a process speculate?* Moving Time Window executes only
  events in `[GVT, GVT + w]` with `w` a tunable throttle; adaptive schemes set `w` from
  observed parallelism and estimated rollback overhead. There is explicit prior work titled
  *"Estimating rollback overhead for optimism control in Time Warp"* and
  *"Limiting Optimism: Time or Event Count?"*
- **Objective:** maximize useful (committed) work per unit resource — i.e. goodput —
  by trading speculative progress against expected cascading rollback cost under contention.

**Mapping our candidate problem onto it:** speculative agent nodes ↔ events beyond GVT;
verifier verdict ↔ straggler arrival; sub-DAG invalidation ↔ antimessage cascade; GPU
capacity ↔ processors; exposure window `N_spec` ↔ the time window `w`; "ration capacity
between speculative and validated work" ↔ optimism throttling. **The optimization problem
is the same problem.** What differs is that PDES invalidation is triggered by a
deterministic causality check rather than a probabilistic semantic verdict, and that PDES
processes serve one shared objective rather than competing tenants with individual SLOs.

### (b) Sequential testing / pipelined filter ordering

Jobs = tests with cost `c_i` and failure probability `p_i`; decision = order of testing;
objective = minimize expected cost; **known optimal policy** = order by non-decreasing
`c_i / p_i` for a serial system with no precedence, polynomial under series-parallel
precedence, **NP-hard under general precedence** (Ünlüyurt; Babu et al.; re-proved
arXiv:2606.07589). This subsumes "when to run the validator relative to other work."

### (c) Stochastic RCPSP with decision-dependent (endogenous) uncertainty

Activities with precedence and renewable resource constraints; uncertainty **revealed only
by executing an activity** (Type-2 endogenous uncertainty); recourse policy chosen under
non-anticipativity constraints; rework on failure; objective = expected makespan or weighted
completion time. This is the standard multistage-stochastic-programming home for
"execute a validation action to reveal whether downstream work is valid."

**Conclusion for BQ4:** the agent version changes the *application domain and the cost
constants*, not the *optimization problem*.

## 2B.5 Is cascade depth actually new? (BQ5)

No. The specific property proposed as distinctive — **exposure grows dynamically while
validation remains pending** — is the defining problem of optimism control in PDES, where
the quantity at risk grows with speculative advance and the throttle exists precisely to
bound it. In that literature cascade size is stochastic, dynamically growing, resource-
dependent, and estimated online for control purposes. Additional non-AI precedents: hardware
thread-level speculation with dynamic resource allocation by speculation metric, and
transactional-memory contention managers that throttle speculative concurrency on contention
feedback (Yoo & Lee, SPAA 2008). A US patent (9104491) also covers batch-scheduler
management of speculative vs. non-speculative tasks with suppression under load.

## 2B.6 Agent-specific property classification (BQ6)

| # | Candidate property | Classification | Basis |
|---|---|---|---|
| A | Heterogeneous stages (GPU gen / CPU tools / remote APIs / sandboxes) | **VERIFIED DISTINCTIVE** as a measured workload fact, **NOT DISTINCTIVE** as a scheduling structure | Measured in Architectural Implications (arXiv:2608.04458); heterogeneous-resource DAG scheduling is classical |
| B | Dynamic DAG revelation | **KNOWN ELSEWHERE** | Autellix schedules dynamic DAGs; conditional/stochastic DAG scheduling is an established field |
| C | Semantic verification probability | **PLAUSIBLE BUT UNVERIFIED** | Sherlock constructs verifiers and defines a match rate `m_i`; no production measurement of failure predictability found |
| D | Dynamic exposure growth while validation pends | **KNOWN ELSEWHERE** | PDES optimism control (§2B.4a) |
| E | KV/cache affinity; rescheduling changes reuse | **VERIFIED DISTINCTIVE but heavily occupied** | Preble, SAGA, InferCept, KVFlow, TokenCake, Continuum/CacheTTL (arXiv:2511.02230), CacheCast |
| F | Continuous batching — GPU service cost is not a fixed independent job time | **VERIFIED DISTINCTIVE** | A request admitted to a continuous batch changes every co-batched request's per-token latency; no classical scheduling model has this, and neither Hopper (slot-granular) nor PDES has it |
| G | Cross-tenant externality: speculative tokens enter batches and change others' latency | **VERIFIED DISTINCTIVE in kind, but already priced** | PASTE's `LLMPressure(i, load)` term explicitly includes queue/batch and KV pressure |
| H | Side-effect admissibility of speculation | **KNOWN ELSEWHERE** | PASTE graded speculation; Atomix commit frontiers; Cost-Aware admissibility precondition |

Only **F** survives as both distinctive and unoccupied, and it is a property of the resource
model rather than of the failure/validation mechanism the project was built around.

## 2B.7 Kill test

| # | Statement | Rating | Evidence |
|---|---|---|---|
| **T1** | Sherlock does not model shared multi-tenant serving contention | **SUPPORTED** | §2B.1: one workflow, static 8×A100 assignment, no arrival process, no queueing, no utilization or throughput metric, spare capacity assumed |
| **T2** | PASTE does not jointly solve semantic-validation risk + sub-DAG invalidation + shared GPU contention | **PARTIALLY SUPPORTED** | §2B.2: PASTE fully solves the contention half — two job classes, slack budget, preemption under pressure, interference-priced priority, 32 GPUs, real bursty arrival trace. It lacks only semantic validation and cascade |
| **T3** | No prior agent system optimizes speculative exposure on both expected invalidation cost and external queueing cost | **SUPPORTED (but signposted)** | §2B.3: no system combines both. However Cost-Aware §14.2 explicitly names the contended-capacity regime as the open case and identifies B-PASTE's `µ·ΔI` interference term as the fix |
| **T4** | No classical formulation subsumes the problem so directly that the contribution is merely engineering | **REFUTED** | §2B.4a: optimism control in optimistic PDES is the same optimization — bound speculative advance to limit expected cascading rollback under finite resources, with adaptive, online rollback-cost estimation |
| **T5** | Agent workloads introduce ≥1 property making the formulation materially different | **SUPPORTED** | §2B.6: continuous batching (F) makes GPU service cost non-separable across concurrent requests, which no classical model or prior speculation scheduler represents |

**Decision rule applied.** T4 is REFUTED ⇒ STOP unless agent-specific features
*fundamentally* alter the solution. T5 is SUPPORTED, but the surviving property (continuous
batching) belongs to the resource model, not to the speculation/validation mechanism that
was to be the contribution — and T2 shows the contention half is already built. The rule is
not satisfied for GO, and the escape clause for T4 is not met.

**Verdict: STOP on the speculative-validation-under-contention direction.**

## 2B.8 New verification debts from Stage 2B

1. **Hopper full text could not be extracted** — three PDF sources returned unparseable
   binary. All Hopper statements remain at V3 (bibliographic confirmation only). Obtain a
   readable copy before citing its internals.
2. **PASTE formulation is inconsistent across fetches** (§2B.2). Obtain the authoritative
   version and fix the record before citing any equation.
3. **Sherlock PDF extraction was unreliable** and produced plausible-looking but generic
   equation descriptions that conflict with the HTML text. Only HTML-derived equations are
   recorded. Confirm Eq. 4–8 against the published PDF manually.
4. PDES optimism-control claims rest on secondary summaries of *"Estimating rollback overhead
   for optimism control in Time Warp"*, *"Limiting Optimism: Time or Event Count?"*, and
   Moving Time Window descriptions. **Marked U.** Obtain and read before relying on them in
   a write-up — though note they are being used here to *reject* our novelty, which is the
   safe direction for an unverified citation.
5. "B-PASTE" is referenced inside arXiv:2606.07846 as a distinct system with an interference
   term `µ·ΔI`. Its relationship to PASTE (arXiv:2603.18897) is unresolved.
