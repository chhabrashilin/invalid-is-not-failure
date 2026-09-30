# Invalid Is Not Failure

**Paper:** *Invalid Is Not Failure: Infrastructure Censoring Bias in Long-Horizon Agent Evaluation*  
**Author:** Shilin Chhabra (University of Wisconsin--Madison)  
**Symposium:** AAAI 2026 Fall Symposium on Trustworthy Agentic Systems (TAS 2026), paper 7658 (camera-ready)

When provider, container, or harness failures end agent runs, leaderboards often score them as failures (the lower endpoint of the identified interval). Dropping them tilts the success odds by the survival ratio. Rerunning removes only part of the bias. Under a constant per-step hazard \(q\), two agents swap places near

\[
q^* \approx \frac{\ln(p_A/p_B)}{\bar H_{1,A}-\bar H_{1,B}}.
\]

This repository releases the symposium paper, an extended preprint, reproduction scripts, and **derived** census tables for 542 public SWE-bench / Multi-SWE-bench submissions plus frontier analyses.

## Links (fill after you publish)

| Artifact | URL |
|---|---|
| GitHub | `https://github.com/chhabrashilin/invalid-is-not-failure` |
| Zenodo DOI | _pending (create a GitHub release after enabling Zenodo)_ |
| Hugging Face dataset | _pending_ |
| Hugging Face Space | _pending_ |

Update `extended_paper/main.tex` (Reproduction paragraph) once the DOI and HF URLs exist.

## What is in this repo

| Path | Contents |
|---|---|
| `tas_camera_ready/` | AAAI-27 camera-ready sources for TAS 2026 |
| `extended_paper/` | Venue-neutral extended preprint |
| `scripts/censoring/` | Symposium reproduction |
| `scripts/extended/` | Census, frontier, critical hazard, DR estimators, figures |
| `results/censoring/` | Derived symposium result files |
| `results/extended/` | Derived census and frontier tables (no raw third-party dumps) |
| `hf_dataset/` | Dataset card + packager for Hugging Face |
| `spaces/identified_intervals/` | Gradio app: identified intervals and sharp rank intervals |

Historical ReSched / Phase-0 measurement scaffolding remains in `docs/`, `simulator/`, `src/`, and related paths. It is **not** the claim of the TAS paper.

## Quick start (reproduce derived tables)

Python 3.10+, [`uv`](https://github.com/astral-sh/uv) recommended. Network is required for fetch scripts. No paid API.

```powershell
cd path\to\invalid-is-not-failure
uv sync
uv run python scripts/censoring/reproduce_all.py
# then the extended pipeline in extended_paper/README.md
```

Raw upstream caches (if you run fetches) land under `data/raw/` and are gitignored. Do not redistribute material you cannot license.

## Gradio tool (local)

```powershell
pip install gradio numpy
python spaces/identified_intervals/app.py
```

Paste a CSV with columns `name,N,resolved,E,U` (evaluation-censored count `E`, unattributable count `U`). The app returns identified intervals and sharp rank intervals under the strict and broad readings from the paper.

## License

- Code and author-written materials: MIT (`LICENSE`).
- AAAI style files in `tas_camera_ready/` belong to AAAI; keep them only for rebuilding the symposium PDF.
- Upstream leaderboard artifacts retain their own licenses. Verify SWE-bench / Multi-SWE-bench experiment repo terms before redistributing anything beyond the derived aggregates shipped here.

## Honesty notes

- Symposium proceedings are archival. Before submitting the extended paper elsewhere, **check** that venue's dual-submission / workshop-extension policy.
- Disclose AI assistance if the target venue requires it.
- Free-tier quotas (GitHub, Zenodo, Hugging Face, Colab, Kaggle) change; check current terms.
- A DOI and a Space do not equal peer review or acceptance at a later venue.
