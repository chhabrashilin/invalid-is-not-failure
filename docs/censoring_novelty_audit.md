# Novelty audit — censoring-aware agent evaluation

Searches run 2026-09-05 covering literature through that date. Query set: agent
benchmark censoring; right censoring agent trajectories; infrastructure-invalid
agent evaluation; missing outcomes in LLM agent benchmarks; informative
censoring LLM agents; attrition bias agent benchmarks; IPCW agent evaluation;
survival analysis agent benchmarks; failure filtering LLM-agent trajectories;
incomplete agent runs benchmark evaluation.

**Verdict: novelty survives.** No located paper derives horizon-induced
censoring bias for agent benchmark success rates, contrasts the two standard
invalid-run policies as opposite-signed biases, and tests a censoring-aware
estimator on a large real agent-trajectory corpus. We claim no "first."

## Closest located work

### Proper Scoring Rules for Agentic Uncertainty Quantification (arXiv:2605.24756)
**Closest on mechanism.**
- *Problem*: strictly proper trajectory-level scoring rules for agentic
  success-probability forecasts.
- *Data*: agent trajectories; predictor-agnostic.
- *Mechanism*: does use **administrative censoring** — extends scores to
  "administratively censored trajectories" by projecting the complete-data score
  onto the observable stopped prefix. Explicitly treats parser failures as
  *informative failures*, not administrative censoring.
- *Infrastructure-invalid runs as censoring*: partially — censoring is a
  secondary extension, and the censoring source is administrative stopping.
- *Horizon-dependent selection bias derived*: **no**.
- *Opposite bias from drop-vs-fail*: **no**.
- *IPCW / censoring-aware correction tested*: **no** — uses a $q_Z$-weighted
  reduced score, not inverse-probability-of-censoring weighting.
- *Our residual distinction*: they score *predictions* under censoring; we
  estimate an *aggregate benchmark reliability parameter* under censoring, derive
  the horizon-covariance bias term, and show two deployed reporting policies
  err in opposite directions.

### Interface-Induced Trajectory Censoring (arXiv:2609.03966)
**Closest on vocabulary, distant on content.**
- *Problem*: a mismatched serving adapter suppresses well-formed tool calls
  before evaluation (BFCL score moves 0.00 → 0.96 by swapping adapters).
- *Mechanism*: "censoring" here means **output truncation/suppression by the
  interface**, not statistical censoring of an outcome variable.
- *Infrastructure-invalid runs as censoring*: no — no missing-data model.
- *Horizon-dependent selection bias derived*: **no** (no bias equations).
- *Opposite bias from drop-vs-fail*: **no**.
- *IPCW tested*: **no** — remedy is a 98-line preflight detection check.
- *Our residual distinction*: entirely different failure channel (interface
  parsing vs. run-level infrastructure invalidation) and a statistical rather
  than diagnostic response. We cite it to disambiguate the term "censoring."

### When Guardrails Look Effective (arXiv:2609.01519)
- *Problem*: construct validity failures in LLM agent commerce guardrail
  evaluation; introduces a construct-validity contract.
- *Data*: agent commerce evaluation; NeurIPS 2026 Trust-AI-Eval workshop, 7pp.
- *Infrastructure-invalid runs as censoring*: **no**.
- *Horizon bias / drop-vs-fail / IPCW*: **no** to all three.
- *Our residual distinction*: this paper substantially reduces the novelty of a
  contribution whose core is *a validity contract*, which is why the present
  work is reframed around censoring estimation rather than around a contract.
  Our validity states are a supporting artifact, not the contribution.

### Failure as a Process (arXiv:2607.09510)
- Anatomy of CLI coding-agent failure onset/evolution/recovery over 3,843
  trajectories, 7 models, 3 scaffolds.
- Analyses *complete, valid* trajectories; invalid runs are not modelled.
- No censoring model, no horizon-selection derivation, no IPCW.
- *Distinction*: they characterise how agents fail; we ask when an execution
  should count as evidence about failure at all.

### The Replay Gap (arXiv:2608.08239)
- Static replay of logged trajectories under a substituted model scores a
  counterfactual world; uses branching rollouts and same-model control forks.
- Concerns *procedure validity* under model substitution, not missing outcomes.
- No censoring estimand, no IPCW.
- *Distinction*: complementary; ours is cross-layer/infrastructure-induced
  missingness rather than counterfactual replay.

### Doomed from the Start (arXiv:2607.06503)
- Early-abort cascade using activation probes with recall-controlled gates.
- *Deliberately induces* truncation as an intervention; does not treat
  unintended infrastructure truncation as a bias source for reported reliability.
- *Distinction*: our censoring is an unwanted measurement artefact, and we
  estimate rather than optimise. Their abort policy is itself a censoring
  mechanism, which our framework would flag as needing a reported hazard.

### A Judge Should Know What Changed (arXiv:2608.24419)
*Chen, Chen, Lin, Vong.* "Construct Validity for LLM-as-a-Judge Evaluation."
- Profiles judges on invariance (S) under construct-preserving edits and
  sensitivity (R) under construct-altering edits; 7 judges, 4 domains.
- Verified by direct retrieval: **no** censoring, missing outcomes, incomplete
  agent runs, or inverse probability weighting.
- *Distinction*: judge-side measurement validity vs. missing outcomes at the
  run level; orthogonal, cited as adjacent validity work.

### Early Diagnosis of Wasted Computation (arXiv:2606.01365)
- Online warning signals for wasted compute in multi-agent systems, 165 GAIA
  traces; 98 usable answers vs 67 without one.
- Notably *does* face a missing-outcome population but treats runs without a
  final answer descriptively, not as censored observations.
- No bias derivation, no correction.

### Standard missing-data literature
IPCW, Horvitz–Thompson, and Hájek estimators are classical and we claim no
methodological novelty in them. Our contribution is the *mapping* of agent
benchmark invalidation onto this machinery, the horizon-compounding argument,
and the empirical magnitude on a large agent corpus.

## Residual novelty statement

To our knowledge, no prior work: (i) models infrastructure-invalid agent
executions as right-censored outcomes with per-step survival $s^H$;
(ii) derives $p_{\text{drop}}-p=\mathrm{Cov}(Y,s^H)/\mathbb{E}[s^H]$ for agent
benchmarks; (iii) shows the two common reporting policies bias in opposite
directions on real trajectories; or (iv) quantifies the correction on ~80k
software-engineering agent trajectories. We do not claim the underlying
statistics are new, and we cite the censoring-adjacent agent work above.
