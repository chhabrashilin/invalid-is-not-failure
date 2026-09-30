---
license: mit
task_categories:
  - tabular-regression
pretty_name: Infrastructure Censoring Bias — Derived Census
tags:
  - agent-evaluation
  - swe-bench
  - partial-identification
  - leaderboard
size_categories:
  - n<1K
---

# Infrastructure censoring bias — derived census results

Derived tables for the paper *Invalid Is Not Failure: Infrastructure Censoring Bias
in Long-Horizon Agent Evaluation* (Shilin Chhabra; AAAI 2026 Fall Symposium TAS 2026
camera-ready, plus extended preprint).

## What this dataset contains

**Included (derived aggregates and analysis outputs):**

- `census_leaderboard.json` — per-split census of public submissions with
  identified intervals and rank intervals under strict and broad readings
- `critical_hazard.json`, `frontier_analysis.json`, `trace_driven.json`,
  `sensitivity.json`, `assumption_tests.json`, `real_case_uncertainty.json`,
  `dr_estimator.json`, `dr_estimator_v2.json`, `label_repair.json`

**Not included here:**

- Raw cloned SWE-bench / Multi-SWE-bench experiment trees (`data/raw/`)
- Full trajectory dumps
- Any file you lack the right to redistribute

Run-level derived CSVs (`bash_only_runs.csv`, `multilingual_runs.csv`) and the
prefix feature matrix (`swe_prefix_records.npz`) live in the GitHub repository under
`results/extended/` when you clone it. Confirm upstream licenses before mirroring
those files to other hosts.

## Upstream sources (pinned in the JSON)

Pinned commits and retrieval times are recorded inside
`census_leaderboard.json` → `sources` and in each fetch script's `manifest.json`
when you regenerate locally:

- [swe-bench/experiments](https://github.com/swe-bench/experiments)
- [multi-swe-bench/experiments](https://github.com/multi-swe-bench/experiments)

**You must verify** those repositories' licenses and terms before use. This card
does not grant rights to the upstream artifacts.

## How to regenerate

From the companion GitHub repository (same release / commit as this dataset
version):

```text
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
```

Then pack with `python hf_dataset/pack_derived.py`.

## Citation

Cite the TAS 2026 paper / extended preprint and this dataset version (and the
Zenodo DOI of the code release when available). Replace the placeholders below
after you mint the DOI and dataset repo:

```bibtex
@inproceedings{chhabra2026invalid,
  title={Invalid Is Not Failure: Infrastructure Censoring Bias in Long-Horizon Agent Evaluation},
  author={Chhabra, Shilin},
  booktitle={AAAI 2026 Fall Symposium on Trustworthy Agentic Systems (TAS 2026)},
  year={2026}
}
```

## Related links

- Code: `https://github.com/chhabrashilin/invalid-is-not-failure` (confirm after push)
- Interactive intervals tool: Hugging Face Space (create from `spaces/identified_intervals/`)
- Zenodo: pending GitHub–Zenodo release DOI
