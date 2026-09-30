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
    rows = rep["splits"]["swebench/verified"]["rows"][:40]
    x = np.arange(1, len(rows) + 1)
    lo = np.array([r["lo"] for r in rows]) * 100
    hs = np.array([r["hi_strict"] for r in rows]) * 100
    hb = np.array([r["hi_broad"] for r in rows]) * 100
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(6.8, 2.4),
                                  gridspec_kw={"width_ratios": [1.9, 1]})
    # (b) adjacent orderings identified, per split
    labels, s_share, b_share = [], [], []
    for key, s in rep["splits"].items():
        fam, split = key.split("/")
        labels.append(("SWE-bench " if fam == "swebench" else "M-SWE ") + split)
        s_share.append(s["adjacent_strict"][1] / max(s["adjacent_strict"][0], 1) * 100)
        b_share.append(s["adjacent_broad"][1] / max(s["adjacent_broad"][0], 1) * 100)
    yy = np.arange(len(labels))
    ax2.barh(yy + 0.2, s_share, 0.4, color=C_FAIL, label="strict")
    ax2.barh(yy - 0.2, b_share, 0.4, color="#aab7b8", label="broad")
    ax2.set_yticks(yy)
    ax2.set_yticklabels(labels, fontsize=6)
    ax2.invert_yaxis()
    ax2.set_xlim(0, 100)
    ax2.set_xlabel("adjacent orderings identified (%)")
    ax2.set_title("(b) all splits", fontsize=8, loc="left")
    ax2.legend(frameon=False, fontsize=6, loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2)
    ax2.grid(alpha=0.25, lw=0.4, axis="x")
    ax.set_title("(a) SWE-bench Verified, top 40 of 135", fontsize=8)
    ax.vlines(x, lo, hb, color="#aab7b8", lw=2.0, label="broad interval")
    ax.vlines(x, lo, hs, color=C_FAIL, lw=2.0, label="strict interval")
    ax.plot(x, lo, "o", color="black", ms=2.4, label="leaderboard score")
    ax.set_xlabel("leaderboard rank")
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
    fig.tight_layout(w_pad=0.8)
    save(fig, "fig_census")


def fig_critical():
    d = json.loads((RES / "extended" / "critical_hazard.json").read_text())
    rep, sc = d["report"]["corpora"], d["scatter"]
    cols = {"frontier (SWE-bench Verified, bash-only)": (C_FR, "frontier, Verified"),
            "frontier (SWE-bench Multilingual)": ("#16a085", "frontier, Multilingual"),
            "tau-bench": (C_TAU, r"$\tau$-bench")}
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(6.8, 2.6))
    for key, (col, lab) in cols.items():
        pts = np.array(sc.get(key, []), dtype=float)
        if len(pts):
            ax.scatter(pts[:, 0] * 100, pts[:, 1] * 100, s=6, color=col, alpha=0.6, lw=0,
                       label=lab)
    lim = (1e-3, 5)
    ax.plot(lim, lim, ":", color="0.4", lw=0.8)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(*lim)
    ax.set_ylim(*lim)
    ax.set_xlabel("exact reversal hazard $q^*$ (%)")
    ax.set_ylabel(r"$\ln(p_A/p_B)/(\bar H_{1A}-\bar H_{1B})$ (%)")
    ax.set_title("(a) one-line law vs exact, every pair", fontsize=8)
    ax.legend(frameon=False, fontsize=6, loc="upper left", markerscale=2)
    ax.grid(alpha=0.25, lw=0.4)
    # (b) adjacent pairs: distribution of exact reversal hazards
    tr = json.loads((RES / "extended" / "trace_driven.json").read_text())
    for key, (col, lab) in cols.items():
        adj = rep[key]["adjacent_exact_fail"]
        vals = np.sort([a * 100 for a in adj if a is not None])
        n = len(adj)
        if len(vals):
            ys = np.arange(1, len(vals) + 1) / n * 100
            ax2.step(np.concatenate([[1e-3], vals]), np.concatenate([[0], ys]), where="post",
                     color=col, lw=1.3, label=lab)
    sub, H, Y, cost, st, cls = load_frontier()
    q_provider = (cls == "censored").sum() / H.sum() * 100
    rv = json.loads((RES / "censoring" / "revision_analysis.json").read_text())
    q_container = rv["SWE-agent"]["observed_early_exit"]["qhat_constant"] * 100
    for q_, lab in ((q_provider, "observed provider rate"), (q_container, "observed container rate")):
        ax2.axvline(q_, color="0.3", ls="--", lw=0.8)
        ax2.text(q_ * 1.08, 45 if "provider" in lab else 25, lab, rotation=90, fontsize=5.8,
                 color="0.3")
    ax2.set_xscale("log")
    ax2.set_xlim(1e-3, 5)
    ax2.set_ylim(0, 100)
    ax2.set_xlabel("per-step hazard $q$ (%)")
    ax2.set_ylabel("adjacent pairs reversed (%)")
    ax2.set_title("(b) adjacent leaderboard pairs", fontsize=8)
    ax2.legend(frameon=False, fontsize=6, loc="upper left")
    ax2.grid(alpha=0.25, lw=0.4)
    fig.tight_layout(w_pad=1.0)
    save(fig, "fig_critical")


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
    path = RES / "extended" / "dr_estimator_v2.json"
    if not path.exists():
        print("skip fig_dr (no dr_estimator_v2.json)")
        return
    d = json.loads(path.read_text())
    sims = d["simulation"]
    keys = [("km_hajek", "KM weighting"), ("param_hajek", "constant-hazard weighting"),
            ("dr_km_logistic", "DR: KM + logistic prefix"),
            ("dr_km_gbm", "DR: KM + boosted prefix"),
            ("dr_param_logistic", "DR: const. hazard + logistic"),
            ("dr_param_gbm", "DR: const. hazard + boosted")]
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 2.3), gridspec_kw={"width_ratios": [1.7, 1]})
    ax = axes[0]
    width = 0.13
    xs = np.arange(len(sims))
    cols = ["#5d6d7e", "#aab7b8", "#1e8449", "#145a32", "#82e0aa", "#48c9b0"]
    for j, ((k, lab), c) in enumerate(zip(keys, cols)):
        rmse = [s[k]["rmse_pp"] for s in sims]
        ax.bar(xs + (j - 2.5) * width, rmse, width, color=c, label=lab)
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{s['hazard']} hazard, $q_0$={s['q0']*100:.0f}%" for s in sims],
                       fontsize=6.5)
    ax.set_ylabel("RMSE (points)")
    ax.set_title(f"(a) estimation error, {d['n_rep']} replicates", fontsize=8)
    ax.legend(frameon=False, fontsize=5.6, loc="upper left")
    ax.grid(alpha=0.25, lw=0.4, axis="y")
    ax = axes[1]
    for kind, col, lab in (("logistic", "#1e8449", "logistic"), ("gbm", "#145a32", "boosted")):
        a = {int(k): v for k, v in d["auc_out_of_fold"][kind].items()}
        ax.plot(list(a), list(a.values()), "o-", color=col, lw=1.2, ms=3, label=lab)
    ax.axhline(0.5, color="0.6", lw=0.7, ls=":")
    ax.set_xscale("log")
    ax.set_xlabel("step $t$ at which the run is cut")
    ax.set_ylabel("out-of-fold AUC")
    ax.set_title("(b) how informative prefixes are", fontsize=8)
    ax.legend(frameon=False, fontsize=6, loc="upper left")
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
    fig_critical()
    fig_plane_and_fragility(swe, tau, fr)
    fig_horizons(swe, tau, fr)
    fig_dr()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
