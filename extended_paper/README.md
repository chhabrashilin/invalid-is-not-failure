# Invalid Is Not Failure (extended version)

Extended, venue-neutral preprint of the TAS 2026 short paper. It adds the
estimation theory (doubly robust estimation from partial trajectories and a
sensitivity analysis for outcome-dependent failure), a census of 243 public
SWE-bench submissions, a 19,500-run frontier corpus from the bash-only
leaderboard, and all real-censoring analyses.

## Build

- Overleaf: upload `main.tex`, `references.bib` and `figures/`; compiler
  pdfLaTeX (uses newtx fonts) or XeLaTeX (uses TeX Gyre Termes).
- Local: `tectonic main.tex`.

## Regenerate every number and figure

From the repository root, in order (no paid API; network needed for the fetch
steps):

```
uv run python scripts/censoring/reproduce_all.py
uv run python scripts/extended/fetch_swebench_census.py
uv run python scripts/extended/fetch_bash_only_exits.py
cd scripts/extended && uv run python repair_labels.py && cd ../..
uv run python scripts/extended/build_prefix_features.py
uv run python scripts/extended/census_leaderboard.py
uv run python scripts/extended/frontier_analysis.py
uv run python scripts/extended/sensitivity.py
uv run python scripts/extended/dr_estimator.py
uv run python scripts/extended/make_extended_figures.py
```

Outputs go to `results/extended/` and `extended_paper/figures/`. Raw census
files are cached under `data/raw/swebench_experiments/` (pinned commit
recorded in `manifest.json`).

## Relation to the symposium paper

The symposium proceedings are archival. Before submitting this version to
another venue, check that venue's dual-submission rules; the new material is
listed in the first footnote of the paper.
