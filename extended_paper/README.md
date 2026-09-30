# Invalid Is Not Failure (extended version)

Extended, venue-neutral preprint of the TAS 2026 short paper. Beyond the
symposium version it adds:

- a critical-hazard law for pairwise ranking reversals, checked against exact
  reversal hazards for every model pair in three corpora;
- sharp rank intervals for leaderboard entries;
- doubly robust estimation from the logged prefix of invalid runs, with
  logistic and gradient-boosted outcome models, and a sensitivity analysis for
  outcome-dependent failure;
- a census of 542 public submissions to 11 leaderboards (SWE-bench Verified,
  Lite, Test, and Multi-SWE-bench in eight languages), with paired significance
  tests cross-tabulated against identification;
- two frontier corpora (19,500 Verified bash-only runs with exit statuses;
  4,161 Multilingual runs), real provider-failure analyses with a paired task
  bootstrap, and hazards calibrated to failure processes observed in logs;
- tests of the independent-failure assumption on real data (repeated runs of
  the same task; cross-model task difficulty).

## Build

- Overleaf: upload `main.tex`, `references.bib` and `figures/`; compiler
  pdfLaTeX (uses newtx fonts) or XeLaTeX (uses TeX Gyre Termes).
- Local: `tectonic main.tex`.

## Regenerate every number and figure

From the repository root, in order. No paid API; network is needed for the
fetch steps; `dr_estimator_v2.py` needs scikit-learn.

```
uv run python scripts/censoring/reproduce_all.py
uv run python scripts/extended/fetch_swebench_census.py
uv run python scripts/extended/fetch_multi_swe_bench.py
uv run python scripts/extended/fetch_bash_only_exits.py --split verified
uv run python scripts/extended/fetch_bash_only_exits.py --split multilingual
cd scripts/extended && uv run python repair_labels.py && cd ../..
uv run python scripts/extended/build_prefix_features.py
uv run python scripts/extended/census_leaderboard.py
uv run python scripts/extended/frontier_analysis.py
uv run python scripts/extended/critical_hazard.py
uv run python scripts/extended/trace_driven.py
uv run python scripts/extended/sensitivity.py
uv run python scripts/extended/assumption_tests.py
uv run python scripts/extended/real_case_uncertainty.py
uv run python scripts/extended/dr_estimator.py
uv run --with scikit-learn python scripts/extended/dr_estimator_v2.py
uv run python scripts/extended/make_extended_figures.py
```

Note: `fetch_bash_only_exits.py --split verified` rewrites
`results/extended/bash_only_runs.csv`, so run `repair_labels.py` after it.

Outputs go to `results/extended/` and `extended_paper/figures/`. Raw census
files are cached under `data/raw/` (pinned commits recorded in each
`manifest.json`).

## Relation to the symposium paper

The symposium proceedings are archival. Before submitting this version to
another venue, check that venue's dual-submission rules; the new material is
listed in the first footnote of the paper.
