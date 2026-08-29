# ReSched — Failure-Aware Resource Scheduling for Agentic AI Workflows

**Status: Stage 1 — research specification only. No simulator, no experiments, no
results.** Nothing in this repository is a measured result.

## Research question

> Can failure-aware scheduling reduce end-to-end task completion time and wasted
> computation in agentic AI workflows compared with resource-aware and workflow-aware
> scheduling policies?

Agentic workflows fail and retry as a matter of course (tool timeouts, failed code
execution, verifier rejections). Conventional DAG and cluster schedulers optimize as
if tasks succeed. This project asks — empirically, in a discrete-event simulator —
whether using per-task failure probability and expected downstream recomputation cost
as a scheduling signal actually helps, and under which conditions it does not.

## Documents (read in this order)

| Document | Contents |
|---|---|
| [docs/research_question.md](docs/research_question.md) | Question, motivation, scope, non-goals, **unverified** novelty claim |
| [docs/hypotheses.md](docs/hypotheses.md) | H1–H6 with IVs, DVs, confounders, falsification criteria |
| [docs/system_model.md](docs/system_model.md) | Entities, workflow/task model, retry semantics, scheduler interface, invariants |
| [docs/experiment_plan.md](docs/experiment_plan.md) | Staging, metrics, experiment families, statistical + reproducibility protocol |
| [docs/related_work.md](docs/related_work.md) | Empty by design — no citations until papers are actually read |
| [docs/research_log.md](docs/research_log.md) | Append-only decision log |

## Layout

```
docs/         research specification and log
simulator/    discrete-event simulator            (Stage 2, empty)
scheduler/    scheduling policies + baselines     (Stage 3-4, empty)
experiments/  experiment drivers and configs      (Stage 5, empty)
analysis/     aggregation, statistics, plots      (Stage 5, empty)
tests/        unit + invariant tests              (Stage 2, empty)
results/      raw run-level outputs (not hand-edited, gitignored)
paper/        write-up                            (Stage 6, empty)
```

## Ground rules

- Results are **simulated** unless explicitly labelled otherwise, and are labelled as
  such in figures and text.
- Baselines are implemented independently and given every input they could realistically
  have. Regimes where a baseline beats ReSched are reported.
- `Oracle-ReSched` is a diagnostic upper bound under perfect information — never
  presented as a deployable system.
- Every reported number traces to a raw artifact under `results/` and a command recorded
  in the research log. Results files are never edited by hand.
- Workload distributions, failure rates, scheduler parameters, metrics, and baselines are
  not changed after observing results without a logged entry stating what changed and why.

## Requirements

Python 3.11+ (**not yet installed in the current development environment**) and the
packages in [requirements.txt](requirements.txt). Setup and run instructions will be
added when the simulator exists in Stage 2.
