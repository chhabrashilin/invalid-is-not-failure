# Rank confidence sets (Phase 2A)

## Method (what the code does)

1. Build a joint task-by-submission status matrix (resolved / eval-censored /
   unattributable / observed failure).
2. On the observed sample, form identified intervals `[lo, hi]` under the
   **strict** and **broad** readings, and sharp rank intervals from the paper's
   rank proposition.
3. Resample the `N` tasks **jointly** across submissions (`B=2000` by default).
4. On each bootstrap draw, recompute intervals and sharp ranks.
5. Report a 95% rank confidence set for submission `j` as
   `[P2.5(best^b), P97.5(worst^b)]`.
6. Call pairwise ordering `A` above `B` **supported** at 95% if the bootstrap
   frequency of `lo_A > hi_B` is at least 95%.

This is a deliberate, conservative combination of partial identification and a
paired task bootstrap. It is **not** claimed to be identical to any one published
procedure until you verify the literature yourself.

## Citations you must verify before using

Do **not** copy these into the paper until you have read the sources and confirmed
the bibliographic details:

- Inference for ranks: often associated with Mogstad, Romano, Shaikh, and Wilhelm.
- Sample-selection / missing-outcome bounds: often associated with Lee.

Related ideas also appear in the paper's existing Kaplan-Meier / doubly robust
citations; keep those separate from the rank-inference claim.

## Coverage simulation (honest summary)

File: `results/extended/rank_confidence_sim.json`

Design: `J=12` agents, `T=200` tasks, `B=400` bootstrap draws, `200` Monte Carlo
reps. True ranks from spaced success probabilities. Missingness independent of
outcomes at rates 0%, 5%, 10%.

Typical results from the committed run (re-check the JSON):

- No missingness: simultaneous coverage near 0.96; mean marginal near 0.996.
- With 5% or 10% missingness: simultaneous coverage ≈ 1.0 (intervals widen;
  procedure is conservative under this DGP).

Simultaneous coverage of *all* ranks at once is harder than marginal coverage.
Do not claim exact 95% simultaneous coverage in general; report the simulation
numbers you actually ran.

## Census application

File: `results/extended/rank_confidence.json`

Command:

```powershell
cd C:\Users\chhab\Downloads\Github\chhabrashilin\research\resched
.\.venv\Scripts\python.exe scripts\extended\rank_confidence.py --B 2000
```

Notes:

- SWE-bench Verified / Lite / Test use the shared task universe (good joint
  bootstrap).
- Multi-SWE-bench languages keep only the **modal** `N`; submissions with a
  different `total_instances` are dropped and listed under `modal_filter`.
- Structural missing Multi-SWE rows become shared pad columns marked
  unattributable only for submissions that still need those counts.

### Headline pattern (Verified, strict reading, from one run)

- Point-identified pairs: 8903
- Bootstrap-supported pairs at 95%: 8025
- Adjacent score orderings supported: 4 / 105
- Median rank CI width: 14

Interpretation: many distant orderings stay supported after sampling noise, but
most **adjacent** leaderboard comparisons are not supported at 95% once
bootstrap uncertainty is layered on identification. Check the JSON before quoting
any number in prose.

## What you still owe the paper

1. Verify citations before naming them.
2. Read and defend every claim orally.
3. Phase 3 write-up: add a short section that states the method, simulation, and
   census tables without overclaiming.
4. Optionally re-upload the new JSON files to the Hugging Face dataset after
   packing (`hf_dataset/pack_derived.py` includes them once updated).
