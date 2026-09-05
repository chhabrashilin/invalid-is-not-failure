# Evidence contract — censoring paper (two corpora)

Every number in the manuscript maps to a row here. Regenerate all of it with:

```
uv run python scripts/censoring/reproduce_all.py          # full
uv run python scripts/censoring/reproduce_all.py --skip-fetch   # offline stages
```

No paid API and no model inference at any stage.

---

## 1. Primary corpus provenance (SWE-agent)

| | |
|---|---|
| **CLAIM** | 80,036 trajectories; 13,389 resolved; 66,647 unresolved; true reliability 16.73% |
| **SOURCE** | `nebius/SWE-agent-trajectories`, rev `68195a1450865274106246d0d0296a1d6807b88e`, CC-BY-4.0, retrieved 2026-09-05 |
| **SCRIPT** | `build_summary.py`, `audit_exit_status.py` |
| **RESULT FILE** | `results/censoring/dataset_provenance.json`, `base_population.json` |
| **EXACT FIELD** | `rows`=80036; `resolved_n`=13389; `true_reliability_p`=0.167287 |
| **ASSUMPTION** | `target` is a trustworthy ground-truth resolution label |
| **LIMITATION** | One scaffold family, 3 model identifiers |

Only 0.60 MB of 1.11 GB downloaded (`fraction_downloaded`=0.00054).

## 2. Population rule and the H=0 row

| | |
|---|---|
| **CLAIM** | n = 80,036; **no exclusions** |
| **AUDIT** | The single H=0 row is `oasis-open__cti-python-stix2-454` (swe-agent-llama-8b, `exit_status=exit_context`, `n_messages`=2, `target`=False): the context limit was reached after the system and user messages but before the agent emitted any turn. |
| **DECISION** | **Retained.** It is a legitimately labelled execution, and under $\pi=s^H$ it has observation probability $s^0=1$, so it is never censored and is well defined in the model. Excluding it would be filtering on inconvenience. |
| **EFFECT** | p changes from 0.167289 (n=80,035) to 0.167287 (n=80,036); all biases unchanged to 3 decimals |
| **ALSO** | No filtering on `exit_status`: resolve rate is 0.248 for `submitted` vs 0.000 for `exit_context`, so filtering on it would condition on the outcome |

## 3. Step-count definitions and validation

| | SWE-agent | tau-bench |
|---|---|---|
| **DEFINITION** | H = messages with `role=="ai"` | H = messages with `role=="assistant"` |
| **EXCLUDES** | system, user | system, simulated user, tool |
| **SCRIPT** | `audit_step_counts.py` | `audit_tau_step_counts.py` |
| **RESULT FILE** | `step_count_audit.csv` | `tau_step_count_audit.csv` |
| **RESULT** | **20/20 exact**, ids 20/20, all turns non-empty | **20/20 exact**, ids 20/20, every turn is a tool-call or NL turn |
| **SEED** | 20260905 | 20260905 |
| **PREDECLARED** | yes, before any censoring result | yes, before any censoring result |

**Deliberate divergence from the SWE dataset card.** The card reports mean steps
31.3 / 58.4; we recompute **15.17 / 28.70**. The card counts agent *and*
environment messages; $2H+1$ reproduces it exactly. We use agent decision turns
because the hazard applies per agent decision. Card numbers are used nowhere as
output.

## 4. Horizon asymmetry (the mechanism)

| Corpus | mean H \| success | mean H \| failure | gap |
|---|---|---|---|
| SWE-agent | 15.169 | 28.696 | 13.5 |
| tau-bench | 13.12 | 14.19 | 1.1 |

**RESULT FILE** `analysis.json` → `population`; `tau_analysis.json` → `population`.

## 5. Analytic bias, both corpora

**SCRIPT** `analyze.py` / `analyze_tau.py` → `analytic()`.
**ASSUMPTION** $\pi_i=s^{H_i}$, $C\perp Y\mid H$.
**LIMITATION** Semi-synthetic; q is a predeclared sensitivity grid, not a
measured outage rate.

SWE-agent (true p = 16.729%):

| q | p_cc | E[p_fail] | bias_cc | bias_fail | retained |
|---|---|---|---|---|---|
| 0.10% | 16.912 | 16.478 | +0.184 | −0.251 | 0.974 |
| 0.25% | 17.172 | 16.113 | +0.444 | −0.616 | 0.938 |
| 0.50% | 17.571 | 15.532 | +0.842 | −1.197 | 0.884 |
| 1.00% | 18.272 | 14.459 | +1.543 | −2.269 | 0.791 |
| 2.00% | 19.423 | 12.605 | +2.694 | −4.124 | 0.649 |

tau-bench (true p = 55.030%):

| q | p_cc | E[p_fail] | bias_cc | bias_fail | retained |
|---|---|---|---|---|---|
| 0.10% | 55.056 | 54.313 | +0.026 | −0.717 | 0.986 |
| 0.25% | 55.094 | 53.255 | +0.064 | −1.775 | 0.967 |
| 0.50% | 55.154 | 51.540 | +0.124 | −3.490 | 0.934 |
| 1.00% | 55.263 | 48.281 | +0.233 | −6.749 | 0.874 |
| 2.00% | 55.433 | 42.393 | +0.402 | −12.637 | 0.765 |

**This dissociation is the paper's central empirical result:** complete-case
bias tracks the horizon gap, invalid-as-failure bias tracks the base rate.

## 6. Partial-identification bounds

| | |
|---|---|
| **CLAIM** | At q=1%: SWE [14.5, 35.3]; tau [48.3, 60.9] |
| **RESULT FILE** | `analytic[].bound_lo`, `bound_hi`, `bound_width` |
| **ASSUMPTION** | **None** about censored outcomes; uses expected censored count |
| **LIMITATION** | Bounds use the expected M under the declared mechanism, not a realised M |

## 7. IPCW

| | |
|---|---|
| **CLAIM** | HT max abs bias 0.005 pp (SWE), 0.017 pp (tau); HT sd 0.016→0.096 pp (SWE) |
| **RESULT FILE** | `monte_carlo[].ht`, `.hajek` |
| **ASSUMPTION** | $\pi_i$ **known by construction** |
| **LIMITATION** | HT is exactly unbiased *because* π is known; real harnesses must estimate it. Hájek is a ratio estimator: consistent, not exactly unbiased. Positivity degrades as $s^H\to0$ |

## 8. Misspecification stress test

| | |
|---|---|
| **CLAIM** | True hazard doubles beyond step 25, weights assume constant: HT −0.137 pp (q0=0.5%), −0.258 pp (q0=1%); Hájek +0.547, +0.969 |
| **RESULT FILE** | `analysis.json` → `stress_test` |
| **LIMITATION** | One misspecification form; does not show IPCW handles unknown or MNAR censoring |

## 9. Model-level ranking

| | SWE-agent | tau-bench |
|---|---|---|
| **Eligibility** | ≥500 trajectories | ≥100 trajectories |
| **Eligible models** | 3 (3 pairs) | 29 (406 pairs) |
| **Tie handling** | average ranks; strict reversals only | same |
| **Reversals** | **0 at every q** | first at **q=0.5%**; q=1%: 1 (cc) / 4 (fail); q=2%: **2 (cc) / 11 (fail)** |
| **Spearman at q=2%** | 1.000 | 0.9978 (cc) / 0.9901 (fail) |
| **Kendall τ_b at q=2%** | 1.000 | 0.9839 (cc) / 0.9393 (fail) |
| **LIMITATION** | 3 well-separated models is a weak test, reported as such | one `model_path` (`openai/gpt-5`) covers 330 rows because two files share the identifier |

## 10. Task-balanced robustness

| | |
|---|---|
| **CLAIM** | SWE: p 16.73%→9.80%, q=1% biases +1.14/−1.30; tau: p 55.03%→56.93%, +0.22/−7.29 |
| **RESULT FILE** | `analysis.json` / `tau_analysis.json` → `task_balanced` |
| **CONCLUSION** | Sign and order of magnitude preserved in both; the directional result is not an artifact of unequal task/model coverage. The SWE *level* changes materially and this is stated |

## 11. tau-bench provenance and outcome semantics

| | |
|---|---|
| **CLAIM** | 4,950 rows, 29 model identifiers, score strictly binary {0.0,1.0}, 0 missing |
| **SOURCE** | `AgentSuite/tau-bench-trajectories`, rev `382e57d1784b55c5155f4ef394ef48f1c747a287`, retrieved 2026-09-05 |
| **RESULT FILE** | `tau_provenance.json` → `score_is_binary`=true, `distinct_finite_scores`=[0.0,1.0], `n_missing_score`=0 |
| **OUTCOME RULE** | Y = 1 iff `eval_result.score == 1.0`; fixed before censoring results |
| **LICENSE** | **None declared.** Raw trajectories cached outside the repo and **not redistributed**; only derived statistics stored |
| **LIMITATION** | `finish_reason` is uniformly `user_stop`, so it carries no information here |

## 12. Real infrastructure case (existence only)

| | |
|---|---|
| **CLAIM** | Two provider-backed runs executed 9 and 4 agent steps before rate-limit invalidation; 6 restored continuations executed 0 steps; none received a label |
| **SOURCE** | `artifacts/phase0_5/scientific_run_dispositions.json` (audited 2026-09-02) |
| **LIMITATION** | Existence, **not** prevalence. Not a provider reliability estimate. Provider not named in the manuscript. Its frequency is **not** used as q |

## 13. Claims deliberately NOT made

- No agent capability or leaderboard claim.
- No provider reliability statistic.
- No prevalence estimate for infrastructure invalidation.
- No claim that IPCW handles unknown or outcome-dependent (MNAR) censoring.
- No population inference: results are finite-corpus sensitivity statements.
- No "first" claim (see `docs/censoring_novelty_audit.md`).
