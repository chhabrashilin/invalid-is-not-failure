# Artifact: measurement-integrity harness for agentic evaluation

This artifact accompanies the TAS 2026 short paper *Measurement Integrity for
Trustworthy Agentic Systems: Failure Modes and a Reproducible Evaluation
Architecture*. It contains the instrumented coding-agent harness, the five
controlled failure-case experiments (E1–E5), and the regression suite enforcing
the nine validity invariants.

## Requirements

- Python 3.12 and [`uv`](https://docs.astral.sh/uv/)
- **E4, E5, and the test suite:** nothing else.
- **E1–E3 only:** a local Docker daemon and one SWE-bench image
  (~10.6 GB, pulled once):

```
docker pull swebench/sweb.eval.x86_64.matplotlib_1776_matplotlib-23412:latest
```

**No paid API key is required to reproduce any result in the paper.**

## Reproduce every number in the paper

```
uv sync
uv run python scripts/paper/reproduce_all.py
```

This writes machine-readable results to `results/paper/`:

| File | Paper claim |
|---|---|
| `e1_test_patch_effect.json` | Omitted `test_patch` → pytest exit 4, "no tests ran" |
| `e2_pipeline_exit_code.json` | `false \| tail -5` → 0 without `pipefail` |
| `e3_repo_scoped_changes.json` | Env churn inflates container count 0→32; repo-scoped stays 0 |
| `e4_oracle_leakage.json` | 20 adversarial future steps change 0 of 24 features |
| `e5_infrastructure_invalid_labels.json` | 3 infra terminations refuse a label; 0 violations |
| `summary.json` | Status of each experiment |

Without Docker, E1–E3 are reported as `skipped` rather than failing:

```
uv run python scripts/paper/reproduce_all.py --skip-docker
```

Run a subset with `--only e4 e5`.

## Validity invariants (regression-enforced)

```
uv run pytest
```

Expected: **128 passed**. The invariants and their principal tests:

| | Invariant | Where enforced |
|---|---|---|
| I1 | Online prefix cannot access future trajectory information | `TrajectoryPrefix`; `tests/test_oracle_leakage.py` |
| I2 | Online prefix cannot access `Y_success` | prefix exposes no outcome record; `tests/test_oracle_leakage.py` |
| I3 | Evaluation state isolated from agent execution state | `src/evaluation/evaluator.py`; `tests/test_phase05_defects.py` |
| I4 | Provider failures do not increment semantic failure features | `src/instrumentation/provider_retry.py`; `tests/test_provider_retry.py` |
| I5 | Infrastructure-invalid runs receive no `Y_success` | `ScientificRunDisposition` validator; `tests/test_provider_retry.py` |
| I6 | Repository-change features are repository-scoped | `src/instrumentation/repo_state.py`; `tests/test_phase05_defects.py` |
| I7 | Raw trajectory artifacts are immutable and hashed | `src/trajectory/store.py`; `tests/test_trajectory.py` |
| I8 | Logical agent calls distinct from physical provider attempts | `ProviderCallRecord`, call ledgers; `tests/test_provider_retry.py` |
| I9 | Restored continuations get new identities, cannot overwrite parents | `scripts/phase0/run_phase05.py`; `tests/test_trajectory.py` |

## Layout

```
src/instrumentation/    trajectory recorder, provider retry layer, agent adapter
src/trajectory/         online-safe schema, prefix type, feature extraction
src/evaluation/         independent evaluator, test-command detection
src/checkpoint/         container lifecycle, commit/restore
scripts/paper/          reproduce_all.py  (E1–E5)
scripts/phase0/         harness runners, availability probes, feature audit
results/paper/          generated experiment results
paper/                  main.tex, references.bib, main.pdf
docs/                   evidence audit, submission checklist, research log
```

## Scope and honest limits

- Validated primarily for **mini-SWE-agent 2.4.6 / SWE-bench Verified** style
  coding-agent workflows. The invariants are what *this* artifact implements;
  they are not claimed to be universally necessary or sufficient.
- E1–E3 exercise **one** benchmark instance. They demonstrate mechanism, not
  prevalence.
- The provider events recorded in `artifacts/phase0_5/` are case-study
  infrastructure failures on a single free-tier account. They are **not** an
  estimate of any provider's service reliability.
- **No replay-stability result is claimed.** Same-condition continuations were
  terminated by provider quota limits before producing valid comparisons.
- Raw trajectories are not committed (large, regenerable); they are written to
  `data/raw/` at run time, hash-manifested, and made read-only.
