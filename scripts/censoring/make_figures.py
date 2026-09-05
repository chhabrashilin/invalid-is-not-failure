"""Two-panel cross-domain figure: reliability estimate vs infrastructure hazard.

Panel A: SWE-agent trajectories (primary). Panel B: tau-bench (secondary).
Identical axis semantics; y-limits differ because the base rates differ
(16.7% vs 55.0%), which is stated in the caption.

    uv run python scripts/censoring/make_figures.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
# AAAI (like most ACM/IEEE venues) requires Type 1 or TrueType fonts. Matplotlib
# defaults to Type 3 in PDF output, which format checkers reject, so force
# TrueType (42) for both PDF and PS backends before any figure is created.
matplotlib.rcParams["pdf.fonttype"] = 42
matplotlib.rcParams["ps.fonttype"] = 42

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "results" / "censoring"
FIG_DIR = REPO_ROOT / "tas_overleaf" / "figures"

TRUE_C = "black"
DROP_C = "#c0392b"
FAIL_C = "#2471a3"
HT_C = "#1e8449"


def panel(ax, analysis, title):
    a = analysis["analytic"]
    mc = analysis["monte_carlo"]
    q = np.array([r["q"] for r in a]) * 100
    p_true = a[0]["p_true"] * 100
    drop = np.array([r["p_drop"] for r in a]) * 100
    fail = np.array([r["p_fail"] for r in a]) * 100
    mcq = np.array([0.0] + [m["q"] for m in mc]) * 100
    ht = np.array([p_true] + [m["ht"]["mean"] * 100 for m in mc])
    lo = np.array([p_true] + [m["ht"]["ci95_lo_pp"] for m in mc])
    hi = np.array([p_true] + [m["ht"]["ci95_hi_pp"] for m in mc])

    ax.axhline(p_true, color=TRUE_C, lw=1.1, zorder=3, label="True reliability")
    ax.plot(q, drop, "o-", color=DROP_C, lw=1.25, ms=3.1, zorder=4,
            label="Drop invalid")
    ax.plot(q, fail, "s-", color=FAIL_C, lw=1.25, ms=3.1, zorder=4,
            label="Invalid as failure")
    ax.plot(mcq, ht, "^--", color=HT_C, lw=1.15, ms=3.1, zorder=5, label="IPCW (HT)")
    ax.fill_between(mcq, lo, hi, color=HT_C, alpha=0.18, lw=0, zorder=2)
    ax.set_title(title, fontsize=7.6, pad=3)
    ax.set_xlabel("Per-step hazard $q$ (%)", fontsize=7.4)
    ax.tick_params(labelsize=6.6)
    ax.grid(alpha=0.25, lw=0.4)
    ax.set_xlim(-0.05, 2.05)


def main() -> int:
    swe = json.loads((OUT_DIR / "analysis.json").read_text(encoding="utf-8"))
    tau_path = OUT_DIR / "tau_analysis.json"
    two_panel = tau_path.exists()

    if two_panel:
        tau = json.loads(tau_path.read_text(encoding="utf-8"))
        fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.35))
        sh = swe["population"]
        th = tau["population"]
        panel(axes[0], swe,
              f"(a) SWE-agent, $n$={swe['population']['n']:,}  "
              f"$\\bar H$: {sh['mean_H_success']:.1f} vs {sh['mean_H_failure']:.1f}")
        panel(axes[1], tau,
              f"(b) tau-bench, $n$={th['n']:,}  "
              f"$\\bar H$: {th['mean_H_success']:.1f} vs {th['mean_H_failure']:.1f}")
        axes[0].set_ylabel("Reported success rate (%)", fontsize=7.4)
        axes[0].legend(fontsize=6.0, frameon=False, loc="upper left",
                       borderaxespad=0.3, handlelength=1.7)
        fig.tight_layout(pad=0.3, w_pad=1.2)
        out = FIG_DIR / "fig1_censoring_bias.pdf"
    else:
        fig, ax = plt.subplots(figsize=(3.4, 2.5))
        panel(ax, swe, "")
        ax.set_ylabel("Reported success rate (%)", fontsize=7.4)
        ax.legend(fontsize=6.0, frameon=False, loc="upper left")
        fig.tight_layout(pad=0.25)
        out = FIG_DIR / "fig1_censoring_bias.pdf"

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight")
    fig.savefig(out.with_suffix(".png"), dpi=200, bbox_inches="tight")
    print(f"wrote {out} ({'two-panel' if two_panel else 'single-panel'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
