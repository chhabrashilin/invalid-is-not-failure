# Leaderboard survey (Phase 2B) - working sheet

Goal: find benchmarks that publish **per-run** results with **termination
reasons**, under a license that lets you obtain and analyse the data. Then
repeat the census and significance-versus-identification analysis.

Do not mark a row "include" until you have personally opened the source and
confirmed license + fields.

| Benchmark / leaderboard | Per-run results? | Termination / exit reason? | License / ToS (check) | Obtainable? | Include? | Notes |
|---|---|---|---|---|---|---|
| SWE-bench experiments (already in paper) | yes | partial (outcome buckets) | check GitHub | yes | in paper | baseline |
| Multi-SWE-bench experiments (already in paper) | yes | partial | check GitHub | yes | in paper | baseline |
| tau-bench / retail+airline (used in symposium) | check | check | check | check | check | may already be local under `results/censoring` |
| LiveCodeBench | check | check | check | check | | |
| WebArena / VisualWebArena public runs | check | check | check | check | | |
| AgentBench public logs | check | check | check | check | | |
| GAIA public submissions | check | check | check | check | | |
| BrowseComp / other web-agent boards | check | check | check | check | | |
| Mini-SWE-agent trajectory dumps | check | exit_status often yes | check | check | | related to frontier corpus |
| OpenHands evaluation exports | check | check | check | check | | |

## Inclusion rule

Only include a board if **all** of the following hold:

1. You can download the data without paying and without violating ToS.
2. Per-task or per-run outcomes exist for multiple submissions or models.
3. You can classify terminations under Definition 1 (valid failure vs
   infrastructure / evaluation censoring vs unattributable), even if roughly.
4. You record the license and pinned commit/URL in a manifest.

## Next concrete actions for you

1. Fill the table above from official pages (do not invent).
2. For each "yes", save a `data/raw/<board>/manifest.json` with URL, license,
   retrieval time, and pinned version.
3. Tell Cursor which board to instrument first; reuse
   `scripts/extended/census_leaderboard.py` patterns.

## What this file is not

It is not a completed survey. Empty "check" cells mean work remaining.
