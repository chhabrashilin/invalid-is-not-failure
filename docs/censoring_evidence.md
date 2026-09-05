# Evidence contract — censoring paper

Every number in the manuscript maps to a row here. Regenerate all of it with:

```
uv run python scripts/censoring/reproduce_all.py
```

No paid API and no model inference at any stage.

---

## Dataset provenance

| | |
|---|---|
| **CLAIM** | 80,036 SWE-agent trajectories; 13,389 resolved; true reliability 16.73% |
| **SOURCE** | `nebius/SWE-agent-trajectories`, revision `68195a1450865274106246d0d0296a1d6807b88e`, license CC-BY-4.0, retrieved 2026-09-05 |
| **SCRIPT** | `scripts/censoring/build_summary.py`, `audit_exit_status.py` |
| **RESULT FILE** | `results/censoring/dataset_provenance.json`, `base_population.json` |
| **EXACT FIELD** | `rows`=80036; `resolved_n`=13389; `true_reliability_p`=0.167289 |
| **ASSUMPTION** | `target` is a trustworthy ground-truth resolution label |
| **LIMITATION** | One corpus, one scaffold family (SWE-agent), three model sizes |

Only 0.60 MB of the 1.11 GB corpus was downloaded (`fraction_downloaded`
= 0.00054) by reading five pruned leaf columns.

## Step-count definition and validation

| | |
|---|---|
| **CLAIM** | H = number of `role=="ai"` messages; parser matches independent count on 20/20 audited trajectories |
| **SCRIPT** | `scripts/censoring/audit_step_counts.py` (seed 20260905) |
| **RESULT FILE** | `results/censoring/step_count_audit.csv` |
| **EXACT FIELD** | 20 rows, `exact_match`=True on all; `instance_id_match`=True on all; every `ai` turn non-empty |
| **ASSUMPTION** | One `ai` message = one agent decision/action turn |
| **LIMITATION** | Validation is 20 of 80,035 rows, drawn at random with a fixed seed |

**Deliberate divergence from the dataset card.** The card reports mean steps
31.3 (resolved) / 58.4 (unresolved). We recompute **15.17 / 28.70**. The card's
figure counts all non-system messages (user + ai); ours counts agent decision
turns only, and `2H + 1 ≈ card value` reproduces the card exactly. We use our
definition because the censoring hazard applies per agent decision. The card
numbers are **not** used anywhere as experimental output.

## Population

| | |
|---|---|
| **CLAIM** | Primary population n = 80,035; one row excluded for H = 0 |
| **RESULT FILE** | `results/censoring/base_population.json`, `exit_status_audit.csv` |
| **EXACT FIELD** | `primary_population_n`=80035; `excluded_n`=1 |
| **ASSUMPTION** | No row is filtered on `exit_status` |
| **LIMITATION** | `exit_status` is strongly associated with success (resolve rate 0.248 for `submitted` vs 0.000 for `exit_context`), so filtering on it would condition on the outcome. We do not. Dataset exit statuses are part of the historical generating process and are **not** our injected censoring. |

## Horizon asymmetry (the mechanism)

| | |
|---|---|
| **CLAIM** | Successful trajectories are shorter: mean H 15.17 vs 28.70; median 12 vs 19 |
| **RESULT FILE** | `results/censoring/analysis.json` → `population` |
| **EXACT FIELD** | `mean_H_success`=15.169, `mean_H_failure`=28.697 |
| **LIMITATION** | Association, not causation; specific to this corpus |

## Analytic bias (primary result)

| | |
|---|---|
| **CLAIM** | At q=0.5%: drop-invalid +0.84pp, invalid-as-failure −1.20pp. At q=2%: +2.69pp and −4.12pp (6.82pp spread) |
| **SCRIPT** | `scripts/censoring/analyze.py` → `analytic()` |
| **RESULT FILE** | `results/censoring/analysis.json` → `analytic` |
| **EXACT FIELD** | `bias_drop_pp`, `bias_fail_pp` per `q` |
| **ASSUMPTION** | P(C=1\|H)=s^H with s=1−q; censoring independent of Y given H |
| **LIMITATION** | Semi-synthetic. q is a **sensitivity grid**, not a measured outage rate |

Exact values (percentage points):

| q | p_drop | p_fail | bias_drop | bias_fail | retained |
|---|---|---|---|---|---|
| 0.0000 | 0.16729 | 0.16729 | +0.000 | +0.000 | 1.000 |
| 0.0010 | 0.16913 | 0.16478 | +0.184 | −0.251 | 0.974 |
| 0.0025 | 0.17173 | 0.16113 | +0.444 | −0.616 | 0.938 |
| 0.0050 | 0.17571 | 0.15532 | +0.842 | −1.197 | 0.884 |
| 0.0100 | 0.18272 | 0.14460 | +1.543 | −2.269 | 0.791 |
| 0.0200 | 0.19423 | 0.12605 | +2.694 | −4.124 | 0.649 |

## IPCW Monte Carlo

| | |
|---|---|
| **CLAIM** | HT bias ≤ 0.007pp at every q; SD grows 0.016→0.096pp; Hájek SD grows faster (0.125pp at q=2%) |
| **SCRIPT** | `analyze.py` → `monte_carlo()`, 200 replicates, seeds 20260905+i |
| **RESULT FILE** | `analysis.json` → `monte_carlo` |
| **EXACT FIELD** | `ht.bias_pp`, `ht.sd_pp`, `hajek.sd_pp` |
| **ASSUMPTION** | Censoring model **known exactly** (π_i = s^{H_i} by construction) |
| **LIMITATION** | Unbiasedness of HT holds because we know π. Real deployments must estimate it. Positivity degrades as s^H → 0 for long H |

## Model-level ranking

| | |
|---|---|
| **CLAIM** | 3 eligible models (≥500 trajectories); **0 pairwise ranking reversals at every q**; Spearman ρ = 1.000 throughout |
| **RESULT FILE** | `analysis.json` → `models`, `ranking` |
| **EXACT FIELD** | `pairwise_reversals`=0 for both policies at all six q; `n_model_pairs`=3 |
| **LIMITATION** | Only 3 eligible models and 3 pairs, well separated (25.9%, 16.7%, 15.2%). This is a **weak test** of ranking stability and we report the null result as such |

**Secondary (effect-size distortion, not ranking).** The 405b−8b gap is 10.71pp
truly; 15.01pp under drop-invalid at q=2% (inflated ~40%); 8.43pp under
invalid-as-failure at q=2% (compressed ~21%). Computed from `models[].by_q`.

## Horizon strata

| | |
|---|---|
| **CLAIM** | Short runs (1–25 steps) are 65.3% of data, p=23.0%, retain 77.6% at q=2%; long runs (>75) are 4.4%, p=2.6%, retain 10.5% |
| **RESULT FILE** | `analysis.json` → `horizon_strata` |
| **LIMITATION** | Bins predeclared before inspection |

## Misspecification stress test

| | |
|---|---|
| **CLAIM** | Under a doubled hazard beyond step 25 but constant-hazard weights: HT bias −0.14pp (q0=0.5%) and −0.26pp (q0=1%); Hájek +0.55pp and +0.97pp |
| **RESULT FILE** | `analysis.json` → `stress_test` |
| **LIMITATION** | One misspecification form. Shows correction degrades gracefully here; does **not** show IPCW handles unknown or MNAR censoring |

## Real infrastructure case (existence only)

| | |
|---|---|
| **CLAIM** | Two provider-backed mini-SWE-agent runs executed 9 and 4 agent steps before quota invalidation; 6 restored continuations executed 0 steps; no valid Y existed for any |
| **SOURCE** | `artifacts/phase0_5/scientific_run_dispositions.json`, per-run reports, call ledger (audited 2026-09-02) |
| **EXACT FIELD** | 8 sessions, `all_invalid`=true, `all_unlabelled`=true |
| **LIMITATION** | Establishes that infrastructure invalidation is **not hypothetical**. It is **not** a provider reliability estimate and its frequency is **not** used as q anywhere. Provider is not named in the manuscript |

## Prior controlled measurement cases (E1–E4)

Retained from the previous study as a supporting "sources of invalidity" table;
regenerated by `scripts/paper/reproduce_all.py`, documented in
`docs/emergency_paper_evidence.md`. Not the main claim of this paper.
