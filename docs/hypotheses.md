# Hypotheses

Status: Stage 1 pre-registration. **No experiments have been run. No result in this
document is measured; everything below is a prediction to be tested.**
Last updated: 2026-08-23.

Each hypothesis states: the claim, why we believe it, independent variables (IVs),
dependent variables (DVs), controls, confounders, a **falsification criterion**
fixed in advance, and **what we will conclude if it is not supported**.

---

## 0. Shared Experimental Vocabulary

### 0.1 Independent variables (the factor space)

| Symbol | Variable | Type | Intended range (v1, provisional) |
|---|---|---|---|
| `POLICY` | Scheduling policy | categorical | FIFO, SJF, CPF, ResourceAware, WorkflowAware, ReSched, Oracle-ReSched |
| `p_fail` | Per-task failure probability (by task type) | continuous | 0.0 – 0.5 |
| `D` | Workflow depth (critical-path length in tasks) | integer | shallow / medium / deep |
| `W` | Workflow width (max parallel branches) | integer | narrow / medium / wide |
| `lambda` | Workflow arrival rate | continuous | swept to produce low → saturated load |
| `N_cpu` | CPU worker count | integer | fixed per config |
| `N_gpu` | GPU worker count | integer | fixed per config |
| `rho_gpu` | Fraction of tasks requiring GPU | continuous | 0.2 – 0.8 |
| `eps_rt` | Runtime-estimate error | continuous | 0 (perfect) → high noise |
| `eps_pf` | Failure-probability estimate error (noise and bias) | continuous | 0 (oracle) → uninformative |
| `R_max` | Retry budget per task | integer | fixed per config |
| `INVAL` | Invalidation semantics variant | categorical | see `system_model.md` §5 |
| `seed` | RNG seed | integer | >= 30 seeds per cell (target) |

### 0.2 Dependent variables (metrics)

**Primary**

- `TCT_workflow` — per-workflow completion time (definition in `experiment_plan.md`).
  Reported as mean, P50, P95, P99 over the workflow population.

**Secondary**

- `throughput` — completed workflows per unit simulated time (steady-state window).
- `util_cpu`, `util_gpu` — worker busy fraction; further split into
  *useful* vs *later-invalidated* occupancy once the waste definition is fixed.
- `wasted_compute` — **definition deferred**, see `system_model.md` §10.
- `retry_amplification` — total attempts / distinct tasks.
- `sched_overhead` — scheduler decision wall-clock cost and decisions per event.
- `fairness` / `starvation` — slowdown distribution across workflows; max waiting
  time; Jain-style index on normalized slowdown (exact form fixed in Stage 3).

**Guardrails** (not optimized, but must not silently degrade)

- workflow completion rate (no workflow abandoned unless the model says so)
- worst-case per-workflow slowdown
- simulator invariant violations (must be zero)

### 0.3 Controls held constant within a comparison

Unless a hypothesis explicitly varies them: identical workload trace (same seed →
same arrivals, same task runtimes, same failure draws where the model permits
common random numbers), identical resource capacity, identical retry budget,
identical warm-up/measurement windows, identical simulator version.

**Common random numbers.** Where feasible, all policies in a cell see the *same*
realized randomness (arrivals, base runtimes, failure coin flips keyed by
(workflow, task, attempt)) so that policy differences are not confounded by
sampling noise. Where scheduling order changes which tasks exist, exact CRN is
impossible; the fallback is many seeds plus paired analysis on the shared prefix.
This limitation is to be documented, not hidden.

---

## H1 — Failure-aware scheduling reduces mean and tail workflow completion time

**Claim.** When workflows contain stochastic failures and retries, a scheduler that
uses per-task failure probability and expected downstream recomputation cost
achieves lower mean and lower tail (P95/P99) workflow TCT than FIFO, SJF, CPF,
Resource-Aware, and Workflow-Aware baselines.

**Rationale (mechanism we expect).** Sequencing high-failure-probability tasks
earlier surfaces failures sooner, so re-execution overlaps with remaining slack
instead of extending the critical path; and deferring work whose inputs are likely
to be invalidated avoids paying for it twice.

- **IVs:** `POLICY` (primary), with `p_fail`, `D`, `lambda` fixed at a declared
  default operating point.
- **DVs:** mean `TCT_workflow`, P50, P95, P99.
- **Controls:** same trace, capacity, retry budget; common random numbers.
- **Confounders to guard against:**
  - *Baseline weakness.* A poorly implemented Workflow-Aware baseline would make H1
    trivially true. Mitigation: each baseline gets a documented information set and
    an independent implementation, reviewed against its own literature description.
  - *Load coupling.* Any policy that reduces waste also reduces effective load,
    which improves TCT for reasons unrelated to sequencing. We must separate
    "less work done" from "better ordering" by reporting total executed task-seconds
    alongside TCT.
  - *Metric definition sensitivity.* TCT must include queueing from arrival, not
    just execution.
  - *Warm-up/tail truncation.* Unfinished workflows at simulation end bias tails.
    Mitigation: fixed measurement window with declared drain policy.
- **Falsification criterion (fixed in advance).** H1 is **not supported** if, at the
  declared default operating point with >= 30 seeds, ReSched fails to achieve a
  lower mean TCT than the best non-oracle baseline with a 95% CI on the paired
  difference that excludes zero. Tail claims are evaluated separately: a result may
  support the mean claim and refute the tail claim, and that must be reported as such.
- **If not supported.** Report it. Then investigate: is failure information
  genuinely useless here, or is the default operating point outside the regime where
  it matters (H2–H4 exist precisely to answer that)? A negative H1 with a positive
  H2 is a publishable and honest characterization result.

---

## H2 — The benefit increases with failure/retry probability

**Claim.** The relative improvement of ReSched over the best baseline is
monotonically non-decreasing in `p_fail` over the studied range, and is
approximately zero at `p_fail = 0`.

**Rationale.** At `p_fail = 0` ReSched's failure term vanishes and it should
degenerate toward its underlying work-conserving policy; the more failure mass
there is, the more there is to exploit.

- **IVs:** `p_fail` swept; `POLICY` in {ReSched, baselines}.
- **DVs:** relative and absolute improvement in mean/P95 TCT, plus `wasted_compute`.
- **Controls:** everything else fixed; same seeds across `p_fail` levels.
- **Confounders:**
  - Increasing `p_fail` also increases *offered load* (more attempts), so the system
    moves toward saturation as the sweep proceeds. Improvement may grow because of
    load, not because of failure-awareness. Mitigation: report utilization alongside,
    and run a load-normalized variant where capacity scales with expected total work.
  - Retry budget interacts: with small `R_max`, high `p_fail` produces abandonment
    rather than retries, changing the phenomenon being measured.
- **Falsification criterion.** H2 is **not supported** if the improvement curve is
  flat (CI overlapping across the sweep) or non-monotone in a way not explained by a
  documented mechanism, or if improvement at `p_fail = 0` is significantly non-zero
  (which would indicate the gain comes from something other than failure-awareness —
  an important finding about our own method).
- **If not supported.** A significant gain at `p_fail = 0` means ReSched is winning
  via an incidental property (e.g., a better tie-break or an implicit SJF/CPF bias).
  We would then isolate that component as an ablation and re-attribute the credit
  honestly, rather than claiming failure-awareness.

---

## H3 — The benefit increases with workflow depth / downstream recomputation cost

**Claim.** The improvement grows with `D` (and with the amount of downstream work
invalidated per failure), because a failure deep in a long dependency chain
invalidates or delays more dependent computation.

- **IVs:** `D` swept; separately, downstream invalidation cost varied via `INVAL`
  semantics and via branch fan-out below the failure point.
- **DVs:** mean/P95 TCT improvement; `wasted_compute`; retry amplification.
- **Controls:** total expected work per workflow held constant while varying depth
  where possible (deep-narrow vs shallow-wide with matched task count), so that
  "depth" is not silently "more work."
- **Confounders:**
  - *Depth vs. total work.* Naively increasing depth increases workflow size, which
    increases TCT for everyone. The matched-work design above is required.
  - *Depth vs. parallelism.* Deeper workflows have less internal parallelism, so the
    system behaves differently under load independent of failure.
  - *Critical-path baselines advantage.* CPF should get relatively stronger as depth
    grows; if ReSched's margin over CPF shrinks with depth, that is the real result.
- **Falsification criterion.** H3 is **not supported** if, with total work matched,
  the improvement does not increase with depth (CIs overlapping across depth levels),
  or if it decreases.
- **If not supported.** Likely means the dominant cost is re-execution of the failed
  task itself rather than downstream invalidation, which would simplify the method
  (drop the downstream-cost term) — a useful ablation-driven finding.

---

## H4 — The benefit is larger under CPU/GPU resource contention

**Claim.** As offered load approaches capacity — especially for the scarce resource
class (GPU) — the improvement from failure-aware scheduling grows, because a wasted
scarce-resource slot has higher opportunity cost.

- **IVs:** `lambda` swept to sweep utilization; `N_gpu` / `N_cpu` varied; `rho_gpu`
  varied to shift the bottleneck between classes.
- **DVs:** improvement in mean/P95 TCT vs utilization; `util_gpu` split into useful
  vs later-invalidated.
- **Controls:** fixed workflow structure and `p_fail` while sweeping load.
- **Confounders:**
  - *Saturation artifacts.* Near or above capacity, queues grow without bound and TCT
    diverges for every policy; apparent differences become dominated by instability
    and by the measurement window. Mitigation: identify the stable-load region, and
    report saturated points separately and clearly labelled.
  - *Bottleneck misidentification.* If CPU is accidentally the bottleneck, GPU-focused
    reasoning does not apply.
  - Very low load: with idle resources, ordering barely matters and all policies
    converge — expected, and a useful sanity check rather than a failure.
- **Falsification criterion.** H4 is **not supported** if improvement does not
  increase with utilization within the stable region, or if it is maximized at low
  load.
- **If not supported.** Would suggest the benefit is a pure ordering/critical-path
  effect rather than a resource-opportunity-cost effect, which changes both the story
  and the design of the priority function.

---

## H5 — The method remains useful under imperfect failure-probability estimates

**Claim.** ReSched retains a statistically significant fraction of its
perfect-information benefit when failure probabilities are estimated with realistic
noise and bias, and it degrades gracefully — never falling significantly *below* the
best baseline — as estimates degrade toward uninformative.

- **IVs:** `eps_pf` (noise magnitude, and separately systematic bias — over- vs
  under-estimation), `eps_rt`; estimator family (empirical per-task-type rate,
  logistic regression, gradient-boosted trees — simple first, per protocol).
- **DVs:** TCT improvement retained vs Oracle-ReSched (%), plus absolute comparison
  against best baseline; calibration quality of the estimator (e.g., Brier score,
  reliability curve) reported alongside.
- **Controls:** identical workloads across estimator quality levels.
- **Confounders:**
  - *Leakage.* If the estimator is fit on the same realized failures it then predicts,
    the "imperfect" estimator is secretly an oracle. Estimators must be trained on a
    disjoint set of workflow instances / a warm-up period and applied online only.
  - *Discrimination vs calibration.* An estimator can be badly calibrated yet rank
    tasks correctly; scheduling mainly needs ranking. Both must be measured, or we
    will misattribute robustness.
  - *Degenerate-estimate collapse.* An uninformative estimator should make ReSched
    degenerate to its base policy; if it instead performs worse, that is a real defect
    to report.
- **Falsification criterion.** H5 is **not supported** if (a) benefit vanishes (CI
  includes zero) at realistic noise levels, or (b) ReSched is significantly worse
  than the best baseline at any tested estimate-quality level.
- **If not supported.** The honest conclusion is that failure-aware scheduling is
  viable only where good failure predictors exist, which narrows applicability and
  must be stated in the abstract, not a limitations footnote.

---

## H6 — Failure-aware scheduling reduces compute spent on later-invalidated work

**Claim.** ReSched reduces total resource-seconds spent on work that is ultimately
discarded, repeated, or invalidated, relative to baselines.

**Explicit caveat.** This hypothesis is only testable once "wasted compute" has a
fixed, edge-case-tested definition (`system_model.md` §10). **H6 must not be
evaluated before that definition is frozen and committed**, because the definition is
the most manipulable quantity in this study.

- **IVs:** `POLICY`; secondarily `p_fail`, `D`, `INVAL`.
- **DVs:** `wasted_compute` (CPU-seconds and GPU-seconds, reported separately —
  aggregating them requires a weighting that would itself be a research choice),
  retry amplification, useful-vs-invalidated utilization split.
- **Controls:** as H1.
- **Confounders:**
  - *Definition gaming.* Any definition that counts only re-executed tasks will favour
    policies that delay work; any definition that counts idle time will favour
    work-conserving policies. Both variants should be reported.
  - *Waste/latency trade-off.* Minimizing waste by refusing to start risky work can
    increase TCT. H6 and H1 can therefore disagree, and that trade-off is itself a
    result worth reporting explicitly.
  - *Attribution of partial work.* Work completed before an upstream failure is only
    "wasted" under some invalidation semantics.
- **Falsification criterion.** H6 is **not supported** if `wasted_compute` under
  ReSched is not lower than the best baseline (95% CI on paired difference excluding
  zero) under the frozen primary definition, or if the sign of the effect flips
  between reasonable alternative definitions (in which case we report the metric as
  definition-sensitive and refrain from the claim).
- **If not supported.** Report that failure-awareness buys latency, not efficiency
  (or vice versa). Either direction is a legitimate finding; claiming both without
  evidence is not.

---

## Cross-cutting Threats to Validity (to revisit each stage)

1. **Simulation-only external validity.** Everything is a model. The simulator's
   fidelity assumptions (`system_model.md` §9) bound every conclusion.
2. **Workload realism.** Synthetic workflow templates are our own construction; if
   they are shaped like the mechanism we propose, H1 is guaranteed by construction.
   Mitigation: template families defined before implementing ReSched, and at least
   one family designed to be *adversarial* to failure-aware scheduling.
3. **Researcher degrees of freedom.** Sweeps, seeds, and metric definitions are fixed
   here in advance; any change after seeing results goes in `docs/research_log.md`
   with a reason and is reported in the paper.
4. **Multiple comparisons.** Many cells × many metrics inflate false positives.
   Correction procedure to be fixed in Stage 3 before analysis.
5. **Oracle misuse.** Oracle-ReSched is a diagnostic upper bound only, never
   presented as a deployable system or as evidence of achievable gains.
