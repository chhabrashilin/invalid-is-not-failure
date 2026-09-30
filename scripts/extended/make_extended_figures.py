"""Figures for the extended paper.

    uv run python scripts/extended/make_extended_figures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["pdf.fonttype"] = 42
matplotlib.rcParams["ps.fonttype"] = 42
matplotlib.rcParams["font.size"] = 8
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
from frontier_analysis import load as load_frontier  # noqa: E402

RES = REPO_ROOT / "results"
FIG = REPO_ROOT / "extended_paper" / "figures"
C_SWE, C_TAU, C_FR = "#d35400", "#7d3c98", "#1f618d"
C_DROP, C_FAIL, C_TRUE = "#c0392b", "#2471a3", "black"


def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(FIG / f"{name}.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("wrote", FIG / f"{name}.pdf")


def corpora():
    s = pq.read_table(RES / "censoring" / "trajectory_summary.parquet")
    swe = {"H": np.asarray(s.column("step_count")).astype(int),
           "Y": np.asarray(s.column("target")).astype(float),
           "m": np.asarray(s.column("model_name")).astype(str)}
    t = pq.read_table(RES / "censoring" / "tau_trajectory_summary.parquet")
    tau = {"H": np.asarray(t.column("step_count")).astype(int),
           "Y": (np.asarray(t.column("score")).astype(float) == 1).astype(float),
           "m": np.asarray(t.column("model_path")).astype(str)}
    sub, H, Y, cost, st, cls = load_frontier()
    k = cls == "outcome"
    fr = {"H": H[k], "Y": Y[k], "m": sub[k], "cost": cost[k]}
    return swe, tau, fr


def fig_census():
    rep = json.loads((RES / "extended" / "census_leaderboard.json").read_text())
    rows = rep["splits"]["verified"]["rows"][:40]
    x = np.arange(1, len(rows) + 1)
    lo = np.array([r["lo"] for r in rows]) * 100
    hs = np.array([r["hi_strict"] for r in rows]) * 100
    hb = np.array([r["hi_broad"] for r in rows]) * 100
    fig, ax = plt.subplots(figsize=(6.8, 2.3))
    ax.vlines(x, lo, hb, color="#aab7b8", lw=2.2, label="broad interval (unattributable missing)")
    ax.vlines(x, lo, hs, color=C_FAIL, lw=2.2, label="strict interval (evaluation censoring missing)")
    ax.plot(x, lo, "o", color="black", ms=2.6, label="leaderboard score (invalid as failure)")
    ax.set_xlabel("leaderboard rank (SWE-bench Verified, top 40 of 135 submissions)")
    ax.set_ylabel("resolved (%)")
    ax.set_xlim(0, len(rows) + 1)
    top = lo.max() + 4
    ax.set_ylim(lo.min() - 1.5, top)
    for xi, h in zip(x, hb):
        if h > top:
            ax.annotate(f"to {h:.0f}%", (xi, top), xytext=(3, -8), textcoords="offset points",
                        fontsize=6, color="0.35")
    ax.grid(alpha=0.25, lw=0.4)
    ax.legend(frameon=False, fontsize=6.5, loc="lower left")
    save(fig, "fig_census")


def reversals(Hs, Ys, q, pol):
    p = np.array([y.mean() for y in Ys])
    ws = [(1 - q) ** h for h in Hs]
    obs = np.array([((y * w).sum() / w.sum()) if pol == "cc" else (y * w).mean()
                    for y, w in zip(Ys, ws)])
    dt = np.sign(p[:, None] - p[None, :])
    do = np.sign(obs[:, None] - obs[None, :])
    n = len(p)
    return np.triu((dt != 0) & (do != 0) & (dt != do), 1).sum() / (n * (n - 1) / 2)


def split(d, min_n):
    ms = [m for m in sorted(set(d["m"].tolist())) if (d["m"] == m).sum() >= min_n]
    return [d["H"][d["m"] == m] for m in ms], [d["Y"][d["m"] == m] for m in ms]


def fig_plane_and_fragility(swe, tau, fr):
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 2.6), gridspec_kw={"width_ratios": [1, 1.25]})
    ax = axes[0]
    q = 0.01
    for d, col, mk, lab, mn in ((tau, C_TAU, "o", r"$\tau$-bench (29)", 100),
                                (swe, C_SWE, "D", "SWE-agent (3)", 500),
                                (fr, C_FR, "s", "frontier (39)", 400)):
        Hs, Ys = split(d, mn)
        pb0 = [((1 - q) ** h)[y == 0].mean() for h, y in zip(Hs, Ys)]
        pb1 = [((1 - q) ** h)[y == 1].mean() for h, y in zip(Hs, Ys)]
        ax.scatter(pb0, pb1, s=10, marker=mk, color=col, alpha=0.8, lw=0, label=lab)
    ax.plot([0.2, 1], [0.2, 1], ":", color="0.5", lw=0.8)
    ax.set_xlim(0.2, 1.0)
    ax.set_ylim(0.2, 1.0)
    ax.set_aspect("equal")
    ax.set_xlabel(r"$\bar\pi_0$ (failures)")
    ax.set_ylabel(r"$\bar\pi_1$ (successes)")
    ax.set_title(r"(a) survival plane, $q=1\%$", fontsize=8)
    ax.legend(frameon=False, fontsize=6, loc="lower right")
    ax.grid(alpha=0.25, lw=0.4)

    ax = axes[1]
    qs = np.linspace(0, 0.02, 41)
    for d, col, lab, mn in ((fr, C_FR, "frontier", 400), (tau, C_TAU, r"$\tau$-bench", 100)):
        Hs, Ys = split(d, mn)
        for pol, ls in (("fail", "-"), ("cc", "--")):
            ax.plot(qs * 100, [reversals(Hs, Ys, qq, pol) * 100 for qq in qs], ls,
                    color=col, lw=1.2,
                    label=f"{lab}, {'invalid as failure' if pol == 'fail' else 'drop invalid'}")
    ax.set_xlabel("per-step hazard $q$ (%)")
    ax.set_ylabel("model pairs reversed (%)")
    ax.set_title("(b) ranking fragility", fontsize=8)
    ax.legend(frameon=False, fontsize=6, loc="upper left")
    ax.grid(alpha=0.25, lw=0.4)
    fig.tight_layout(w_pad=1.0)
    save(fig, "fig_plane_fragility")


def fig_horizons(swe, tau, fr):
    fig, axes = plt.subplots(1, 3, figsize=(6.8, 1.8), sharey=True)
    for ax, d, title in zip(axes, (swe, tau, fr), ("SWE-agent", r"$\tau$-bench",
                                                   "frontier (bash-only)")):
        for y, col, lab in ((1, "#1e8449", "success"), (0, C_DROP, "failure")):
            h = np.sort(d["H"][d["Y"] == y])
            xs = np.arange(1, h.max() + 1)
            ax.step(xs, 1 - np.searchsorted(h, xs, side="right") / len(h), where="post",
                    color=col, lw=1.0, label=lab)
        ax.set_xscale("log")
        ax.set_title(title, fontsize=8)
        ax.set_xlabel("horizon $h$ (agent steps)")
        ax.grid(alpha=0.25, lw=0.4)
    axes[0].set_ylabel(r"$\Pr(H>h\mid Y)$")
    axes[0].legend(frameon=False, fontsize=6.5, loc="lower left")
    fig.tight_layout(w_pad=0.6)
    save(fig, "fig_horizons")


def fig_dr():
    path = RES / "extended" / "dr_estimator.json"
    if not path.exists():
        print("skip fig_dr (no dr_estimator.json)")
        return
    d = json.loads(path.read_text())
    sims = d["simulation"]
    keys = [("km_hajek", "KM weighting"), ("param_hajek", "constant-hazard weighting"),
            ("dr_km", "DR, KM + prefix model"), ("dr_param", "DR, constant hazard + prefix"),
            ("dr_km_null", "DR, KM + null model")]
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 2.2), gridspec_kw={"width_ratios": [1.7, 1]})
    ax = axes[0]
    width = 0.16
    xs = np.arange(len(sims))
    cols = ["#5d6d7e", "#aab7b8", "#1e8449", "#82e0aa", "#f5b041"]
    for j, ((k, lab), c) in enumerate(zip(keys, cols)):
        rmse = [s[k]["rmse_pp"] for s in sims]
        ax.bar(xs + (j - 2) * width, rmse, width, color=c, label=lab)
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{s['hazard']}\n$q_0$={s['q0']*100:.0f}%" for s in sims], fontsize=6.5)
    ax.set_ylabel("RMSE (points)")
    ax.set_title(f"(a) estimation error, {d['n_rep']} replicates", fontsize=8)
    ax.legend(frameon=False, fontsize=5.8, loc="upper left")
    ax.grid(alpha=0.25, lw=0.4, axis="y")
    ax = axes[1]
    a = {int(k): v for k, v in d["auc_by_step"].items()}
    ax.plot(list(a), list(a.values()), "o-", color="#1e8449", lw=1.2, ms=3)
    ax.set_xscale("log")
    ax.set_xlabel("step $t$ at which the run is cut")
    ax.set_ylabel("AUC of prefix model")
    ax.set_title("(b) how informative prefixes are", fontsize=8)
    ax.grid(alpha=0.25, lw=0.4)
    fig.tight_layout(w_pad=1.0)
    save(fig, "fig_dr")


def fig_hazard(swe, tau, fr):
    """Reported reliability against q for the three corpora (pooled)."""
    swe_an = json.loads((RES / "censoring" / "analysis.json").read_text())
    tau_an = json.loads((RES / "censoring" / "tau_analysis.json").read_text())
    fig, axes = plt.subplots(1, 3, figsize=(6.8, 1.95))
    qs = np.linspace(0, 0.02, 41)
    for ax, d, an, title in zip(axes, (swe, tau, fr), (swe_an, tau_an, None),
                                ("(a) SWE-agent", r"(b) $\tau$-bench", "(c) frontier, pooled")):
        H, Y = d["H"], d["Y"]
        p = Y.mean() * 100
        cc = [((Y * (1 - q) ** H).sum() / ((1 - q) ** H).sum()) * 100 for q in qs]
        fl = [(Y * (1 - q) ** H).mean() * 100 for q in qs]
        ax.axhline(p, color=C_TRUE, lw=1.0, label="true")
        ax.plot(qs * 100, cc, color=C_DROP, lw=1.3, label="drop invalid")
        ax.plot(qs * 100, fl, color=C_FAIL, lw=1.3, label="invalid as failure")
        if an is not None:
            mc = an["monte_carlo"]
            mq = np.array([0.0] + [m["q"] for m in mc]) * 100
            ax.fill_between(mq, [p] + [m["ht"]["ci95_lo_pp"] for m in mc],
                            [p] + [m["ht"]["ci95_hi_pp"] for m in mc], color="#1e8449",
                            alpha=0.25, lw=0, label="IPCW 95% MC band")
        ax.set_title(title, fontsize=8)
        ax.set_xlabel("per-step hazard $q$ (%)")
        ax.grid(alpha=0.25, lw=0.4)
    axes[0].set_ylabel("reported success (%)")
    axes[0].legend(frameon=False, fontsize=5.8, loc="lower left")
    fig.tight_layout(w_pad=0.8)
    save(fig, "fig_hazard")


def main() -> int:
    swe, tau, fr = corpora()
    fig_hazard(swe, tau, fr)
    fig_census()
    fig_plane_and_fragility(swe, tau, fr)
    fig_horizons(swe, tau, fr)
    fig_dr()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
