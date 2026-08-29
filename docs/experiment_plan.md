# Experiment Plan (High-Level)

Status: Stage 1. **High-level only. No experiments have been run and no results
exist. This document contains no numbers that are outcomes — only planned ranges and
protocol.** Concrete parameter values, sweep grids, and configs are fixed in Stage 3
and recorded in `experiments/configs/`.
Last updated: 2026-08-23.

---

## 1. Staging

| Stage | Goal | Exit criterion |
|---|---|---|
| 1 | Research specification + repo init | This doc set exists; no code |
| 2 | Discrete-event simulator core + workload generator | Invariants I1–I9 unit-tested; determinism verified |
| 3 | Baseline policies + metrics + harness; freeze metric definitions | Baselines sane on hand-checked micro-cases; waste definition frozen |
| 4 | ReSched + Oracle-ReSched + ablations | Priority function specified and ablated |
| 5 | Main experiments (E1–E6) + analysis | Raw artifacts + CIs for every claim |
| 6 | Literature verification + paper draft | Novelty claims checked or repositioned |

Stages are not started until the prior stage's exit criterion is met.

---

## 2. Metric Definitions (to be frozen at end of Stage 3)

- **`TCT_workflow`** = `workflow_end_time - workflow_arrival_time`. Includes queueing.
  Reported as mean, P50, P95, P99 over the measured workflow population.
  *Open decision (Stage 3): how `FAILED_OUT` workflows enter this statistic. They must
  not be silently excluded; the working plan is to report TCT over completed
  workflows plus a separate abandonment rate, and additionally a variant where
  abandoned workflows are included at their termination time.*
- **`throughput`** = completed workflows per unit simulated time within the
  measurement window.
- **`util_cpu` / `util_gpu`** = busy worker-seconds / (capacity × window), split into
  useful vs later-invalidated per I8.
- **`wasted_compute`** = **NOT YET DEFINED** — see `system_model.md` §10. W-A and W-B
  both implemented; primary designated before any policy comparison is run.
- **`retry_amplification`** = total attempts / distinct logical tasks.
- **`sched_overhead`** = wall-clock seconds per scheduling decision (mean, P99) and
  decisions per simulated second. Reported as a real measurement of our
  implementation, with the caveat that it is Python-implementation-dependent and not
  a claim about an optimized system.
- **fairness / starvation** = distribution of normalized slowdown
  (`TCT / ideal_isolated_TCT`); report P99 and max, plus an index (exact form fixed
  in Stage 3).

**Warm-up and measurement window.** Discard a warm-up prefix; measure workflows that
*arrive* within the measurement window and are followed to completion (drain). The
exact rule is fixed in Stage 3 and applied identically to all policies. Truncation
bias particularly affects P99 and must be checked.

---

## 3. Experiment Families

Each family answers one named hypothesis. No experiment is implemented without its
hypothesis, IVs, DVs, and interpretation-if-unsupported already written in
`docs/hypotheses.md`.

| ID | Hypothesis | Design | Primary IV | Notes |
|---|---|---|---|---|
| **E0** | — (validation) | Sanity + calibration suite | — | Not a result; see §4 |
| **E1** | H1 | Policy comparison at a declared default operating point | `POLICY` | Headline comparison |
| **E2** | H2 | Sweep failure probability | `p_fail` | Includes `p_fail = 0` control |
| **E3** | H3 | Sweep depth with **total work matched**; vary invalidation semantics | `D`, `INVAL` | Deep-narrow vs shallow-wide |
| **E4** | H4 | Sweep offered load / capacity; shift bottleneck class | `lambda`, `N_gpu`, `rho_gpu` | Report stable vs saturated regions separately |
| **E5** | H5 | Degrade failure-probability estimates (noise and bias); estimator family comparison | `eps_pf`, estimator | Train/apply split to prevent leakage |
| **E6** | H6 | Waste accounting across policies | `POLICY` | Only after waste definition frozen |
| **E7** | ablation | Remove each ReSched term in turn | priority terms | Attributes credit to the failure term |
| **E8** | adversarial | Workload family designed to defeat failure-awareness | template family | Expected to show *no* benefit; a null here is a feature |

E0, E7, and E8 exist to make a positive result believable. E8 in particular is a
pre-committed attempt to find where the method fails.

---

## 4. E0 — Validation Suite (before any comparison)

Not a scientific result; a correctness gate.

1. **Determinism.** Same config + seed ⇒ identical event log (I7).
2. **Invariant assertions.** I1–I9 hold across randomized configs.
3. **Analytic micro-cases.** Single worker, single task: TCT = runtime.
   M/M/1-style queue with exponential single-task workflows: mean queueing time
   within tolerance of the analytic result. Deterministic hand-computed DAG:
   makespan matches manual calculation.
4. **Degenerate-policy equivalence.** With `p_fail = 0`, ReSched must reduce to its
   base policy behaviour; any deviation indicates the failure term is doing something
   unintended.
5. **Zero-load / infinite-capacity checks.** With capacity ≫ load all policies
   converge; large divergence indicates a bug, not a finding.
6. **Load sanity.** Utilization increases monotonically with `lambda` up to
   saturation.

---

## 5. Statistical Protocol (pre-committed)

- **Replication.** Target >= 30 independent seeds per cell; increase where variance is
  high. Seeds drawn from a fixed, recorded list — never re-drawn after inspecting
  results, never cherry-picked.
- **Paired comparison.** Where common random numbers apply, compare policies on
  matched seeds and analyze the paired difference. Report the pairing method and its
  limits (`hypotheses.md` §0.3).
- **Uncertainty.** 95% confidence intervals on means (bootstrap or t-based, choice
  fixed in Stage 3). Percentile metrics (P95/P99) get bootstrap CIs — point estimates
  of tails from few seeds are unreliable and will not be reported bare.
- **Distributions, not just means.** Report full TCT CDFs for headline comparisons.
- **Multiple comparisons.** Correction procedure fixed before Stage 5 analysis.
- **Effect size.** Report absolute and relative differences, not only significance.
  A statistically significant 0.5% improvement is not a systems contribution and will
  not be presented as one.
- **Negative results are retained.** Any cell where a baseline beats ReSched appears
  in the results tables and, if material, in the paper.

---

## 6. Reproducibility Protocol

- Every run writes: the **resolved config** (all defaults expanded), the **seed**, the
  **code version** (git commit + dirty flag), the **environment** (Python version,
  package versions, OS, CPU), a **run id**, and **raw run-level records**
  (CSV/Parquet/JSON) — never only aggregates.
- `results/` holds raw outputs; aggregation and plotting live in `analysis/` and are
  re-runnable from raw data. **Results are never hand-edited.** Any plot must be
  regenerable by a recorded command.
- Layout (provisional):
  `results/<experiment_id>/<policy>/<config_hash>/seed_<n>/{events.parquet,summary.json,config.yaml,env.json}`
- Every experiment invocation is recorded in `docs/research_log.md` with its command.
- Long runs are chunked and resumable; partial results are labelled partial.

---

## 7. Fairness-to-Baselines Protocol

1. Each baseline is implemented from its own description, not as a degraded ReSched.
2. Each baseline receives every input it could realistically have
   (`system_model.md` §7.3).
3. Where a baseline has tunable parameters, it gets a tuning budget comparable to
   ReSched's, on the same tuning configurations.
4. Baselines are hand-checked on micro-cases where their correct behaviour is obvious
   (e.g., SJF must order a fixed ready set by predicted runtime).
5. Oracle-ReSched is reported only as a gap-to-perfect-information diagnostic.

---

## 8. Pre-Committed Reporting Rules

- The default operating point for E1 is declared **before** E1 is run and is not
  changed afterwards; if it is changed, both versions are reported and the reason is
  logged.
- No sweep range, failure rate, workload distribution, metric, or baseline is altered
  after observing results without a `docs/research_log.md` entry stating what changed,
  why, and what the pre-change result was.
- If ReSched loses in a regime, that regime is reported with the same prominence as
  the regimes where it wins.
- Simulated results are labelled *simulated* everywhere, including figure captions.

---

## 9. Known Gaps in This Plan (to close in later stages)

- Default operating point not yet chosen (Stage 3).
- Waste metric not yet defined (Stage 3).
- ReSched priority function not yet specified (Stage 4).
- Fairness index form not yet chosen (Stage 3).
- Multiple-comparison correction not yet chosen (Stage 5).
- No real-trace validation; external validity rests entirely on model assumptions.
- Compute budget for the full sweep not yet estimated (Stage 3).
