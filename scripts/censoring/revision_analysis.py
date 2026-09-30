"""Analyses added in revision for the TAS 2026 camera-ready version.

None of these changes a predeclared quantity. Each answers a reviewer comment
and is labelled "added in revision" in the paper.

  1. survival decomposition: mean survival of successes (pbar1) and failures
     (pbar0), their ratio rho, the invalid fraction m, and a check of the odds
     identity odds(p_cc) = rho * odds(p)
  2. stochastic-dominance check of the outcome-conditional horizon laws
  3. rerun-until-valid decomposition into within-cell and between-cell terms
  4. deployable IPCW from observed censoring times only (Kaplan-Meier and
     parametric hazard), under constant and step-dependent hazards
  5. critical hazards on a fine grid (1-point bias, first ranking reversal)
  6. observed container failures in the SWE-agent corpus (exit_status
     early_exit) analysed as real censoring
  7. per-model survival plane and the camera-ready figure

    uv run python scripts/censoring/revision_analysis.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
OUT_DIR = REPO_ROOT / "results" / "censoring"
FIG_DIR = REPO_ROOT / "tas_camera_ready" / "figures"

from analyze import MASTER_SEED, N_REPLICATES, Q_GRID  # noqa: E402

REVISION_SEED = MASTER_SEED + 10_000
FINE_Q = np.round(np.arange(0.0, 0.05 + 1e-12, 0.0001), 6)
STRESS_BREAKPOINT = 25
MIN_TRAJ_SWE = 500
MIN_TRAJ_TAU = 100
N_BOOT = 200


# --------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------

def load_swe():
    t = pq.read_table(OUT_DIR / "trajectory_summary.parquet")
    H = np.asarray(t.column("step_count")).astype(np.int64)
    Y = np.asarray(t.column("target")).astype(np.float64)
    model = np.asarray(t.column("model_name")).astype(str)
    inst = np.asarray(t.column("instance_id")).astype(str)
    exits = np.asarray(t.column("exit_status")).astype(str)
    cell = np.char.add(np.char.add(inst, "||"), model)
    return {"name": "SWE-agent", "H": H, "Y": Y, "model": model, "task": inst,
            "cell": cell, "exit": exits, "min_traj": MIN_TRAJ_SWE}


def load_tau():
    t = pq.read_table(OUT_DIR / "tau_trajectory_summary.parquet")
    H = np.asarray(t.column("step_count")).astype(np.int64)
    Y = (np.asarray(t.column("score")).astype(float) == 1.0).astype(np.float64)
    model = np.asarray(t.column("model_path")).astype(str)
    task = np.char.add(np.char.add(np.asarray(t.column("task_name")).astype(str), "||"),
                       np.asarray(t.column("task_id")).astype(str))
    cell = np.char.add(np.char.add(task, "||"), model)
    finish = np.asarray(t.column("finish_reason")).astype(str)
    return {"name": "tau-bench", "H": H, "Y": Y, "model": model, "task": task,
            "cell": cell, "exit": finish, "min_traj": MIN_TRAJ_TAU}


# --------------------------------------------------------------------------
# 1. survival decomposition
# --------------------------------------------------------------------------

def survival(H, Y, q):
    w = (1.0 - q) ** H
    p = Y.mean()
    pb1 = w[Y == 1].mean()
    pb0 = w[Y == 0].mean()
    pbar = w.mean()
    p_cc = (Y * w).sum() / w.sum()
    p_fail = (Y * w).mean()
    rho = pb1 / pb0
    odds_cc_identity = rho * p / (1 - p)
    p_cc_identity = odds_cc_identity / (1 + odds_cc_identity)
    return {
        "q": float(q), "p": float(p), "pbar1": float(pb1), "pbar0": float(pb0),
        "pbar": float(pbar), "rho": float(rho), "invalid_frac_m": float(1 - pbar),
        "p_cc": float(p_cc), "p_fail": float(p_fail),
        "bias_cc_pp": float((p_cc - p) * 100), "bias_fail_pp": float((p_fail - p) * 100),
        "p_fail_identity": float(p * pb1),
        "p_cc_identity": float(p_cc_identity),
        "identity_max_abs_err": float(max(abs(p_cc - p_cc_identity), abs(p_fail - p * pb1))),
        "first_order_log_rho": float(q * (H[Y == 0].mean() - H[Y == 1].mean())),
        "log_rho": float(np.log(rho)),
        "bound_lo": float(p_fail), "bound_hi": float(p_fail + 1 - pbar),
    }


# --------------------------------------------------------------------------
# 2. stochastic dominance
# --------------------------------------------------------------------------

def dominance(H, Y):
    hs = np.arange(0, H.max() + 1)
    H1 = np.sort(H[Y == 1])
    H0 = np.sort(H[Y == 0])
    F1 = np.searchsorted(H1, hs, side="right") / len(H1)
    F0 = np.searchsorted(H0, hs, side="right") / len(H0)
    d = F1 - F0  # >= 0 everywhere means successes are stochastically shorter
    rho_fine = np.array([survival(H, Y, q)["rho"] for q in FINE_Q[1:]])
    return {
        "min_F1_minus_F0": float(d.min()),
        "max_F1_minus_F0": float(d.max()),
        "argmin_h": int(hs[d.argmin()]),
        "first_order_dominance_holds": bool(d.min() >= 0),
        "rho_gt_1_on_fine_grid_to_5pct": bool((rho_fine > 1).all()),
        "min_rho_on_fine_grid": float(rho_fine.min()),
    }


# --------------------------------------------------------------------------
# 3. rerun until valid
# --------------------------------------------------------------------------

def rerun(H, Y, cell, q):
    s = (1.0 - q) ** H
    _, inv, n_t = np.unique(cell, return_inverse=True, return_counts=True)
    g_t = np.bincount(inv, weights=s) / n_t
    a_t = np.bincount(inv, weights=Y * s) / n_t
    p_t = np.bincount(inv, weights=Y) / n_t
    w_t = n_t / n_t.sum()
    p = Y.mean()
    Eg = (w_t * g_t).sum()
    within = (w_t * (a_t - p_t * g_t)).sum() / Eg
    between = ((w_t * p_t * g_t).sum() - p * Eg) / Eg
    p_cc = (w_t * a_t).sum() / Eg
    p_rerun = (w_t * a_t / g_t).sum()
    return {
        "q": float(q),
        "n_cells": int(len(n_t)),
        "share_runs_in_singleton_cells": float(n_t[n_t == 1].sum() / n_t.sum()),
        "bias_cc_pp": float((p_cc - p) * 100),
        "within_pp": float(within * 100),
        "between_pp": float(between * 100),
        "decomposition_err": float(abs(within + between - (p_cc - p))),
        "bias_rerun_pp": float((p_rerun - p) * 100),
        "share_of_cc_bias_removed_by_rerun": float(1 - (p_rerun - p) / (p_cc - p))
        if p_cc != p else None,
        "expected_attempts_per_task": float((w_t / g_t).sum()),
    }


# --------------------------------------------------------------------------
# 4. deployable IPCW from observed censoring times
# --------------------------------------------------------------------------

def km_censoring_survival(V, event, hmax):
    """Kaplan-Meier estimate of G(h) = P(T > h) for the infrastructure failure
    step T, treating completion as right-censoring of T. V is the last step a
    run reached; event=1 if the run was invalidated at step V. Returns an array
    indexed by h = 0..hmax."""
    at_risk_counts = np.bincount(V, minlength=hmax + 1)[: hmax + 1]
    at_risk = at_risk_counts[::-1].cumsum()[::-1]  # #{V >= k}
    d = np.bincount(V[event], minlength=hmax + 1)[: hmax + 1]
    lam = np.divide(d, at_risk, out=np.zeros(hmax + 1), where=at_risk > 0)
    lam[0] = 0.0  # no step executed at h = 0
    return np.cumprod(1.0 - lam)


def draw_T(rng, n, q0, stepdep):
    T = rng.geometric(q0, size=n)
    if stepdep:
        late = T > STRESS_BREAKPOINT
        T[late] = STRESS_BREAKPOINT + rng.geometric(min(2 * q0, 1.0), size=late.sum())
    return T


def true_pi(H, q0, stepdep):
    if not stepdep:
        return (1 - q0) ** H
    b = np.minimum(H, STRESS_BREAKPOINT)
    e = np.maximum(H - STRESS_BREAKPOINT, 0)
    return (1 - q0) ** b * (1 - 2 * q0) ** e


def deployable_mc(H, Y, q0, stepdep, n_rep, seed):
    rng = np.random.default_rng(seed)
    n = len(Y)
    p = Y.mean()
    pi = true_pi(H, q0, stepdep)
    hmax = int(H.max())
    names = ("ht_known", "hajek_km", "ht_km", "hajek_param", "drop", "fail")
    est = {k: np.empty(n_rep) for k in names}
    for r in range(n_rep):
        T = draw_T(rng, n, q0, stepdep)
        C = T > H
        V = np.where(C, H, T)
        G = km_censoring_survival(V, ~C, hmax)
        with np.errstate(divide="ignore"):
            wk = np.where(C, 1.0 / G[H], 0.0)
        qhat = (~C).sum() / V.sum()
        wp = np.where(C, (1 - qhat) ** (-H.astype(float)), 0.0)
        est["ht_known"][r] = (C * Y / pi).sum() / n
        est["hajek_km"][r] = (wk * Y).sum() / wk.sum()
        est["ht_km"][r] = (wk * Y).sum() / n
        est["hajek_param"][r] = (wp * Y).sum() / wp.sum()
        est["drop"][r] = Y[C].mean()
        est["fail"][r] = (Y * C).mean()
    out = {"q0": q0, "hazard": "step-dependent (doubles after step 25)" if stepdep
           else "constant", "n_rep": n_rep}
    for k, v in est.items():
        out[k] = {"bias_pp": float((v.mean() - p) * 100),
                  "sd_pp": float(v.std(ddof=1) * 100),
                  "rmse_pp": float(np.sqrt(((v - p) ** 2).mean()) * 100)}
    return out


def hard_cap(H, Y, K):
    """A structurally different mechanism: every run longer than K steps is
    invalidated (a per-run quota or a fixed harness kill). T = K+1 for all runs,
    so T is independent of (Y, H), but G(h) = 0 for h > K and positivity fails.
    Kaplan-Meier weights are then 1 for every valid run, so the weighted
    estimate collapses to the complete-case rate."""
    C = H <= K
    V = np.where(C, H, K + 1)
    G = km_censoring_survival(V, ~C, int(max(H.max(), K + 1)))
    with np.errstate(divide="ignore"):
        w = np.where(C, 1.0 / G[H], 0.0)
    p = Y.mean()
    S, M, N = (Y * C).sum(), (~C).sum(), len(Y)
    return {"K": int(K), "p_pct": float(p * 100), "invalid_frac": float(M / N),
            "drop_pct": float(Y[C].mean() * 100), "fail_pct": float(S / N * 100),
            "km_pct": float((w * Y).sum() / w.sum() * 100),
            "bounds_pct": [float(S / N * 100), float((S + M) / N * 100)]}


# --------------------------------------------------------------------------
# 5. critical hazards
# --------------------------------------------------------------------------

def critical(H, Y):
    rows = [survival(H, Y, q) for q in FINE_Q]
    out = {}
    for key, col in (("cc", "bias_cc_pp"), ("fail", "bias_fail_pp")):
        hit = [r for r in rows if abs(r[col]) >= 1.0]
        out[f"q_1pt_{key}"] = hit[0]["q"] if hit else None
        out[f"m_1pt_{key}"] = hit[0]["invalid_frac_m"] if hit else None
    return out


def per_model(d, qs):
    H, Y, model = d["H"], d["Y"], d["model"]
    names = [m for m in sorted(set(model.tolist())) if (model == m).sum() >= d["min_traj"]]
    res = []
    for m in names:
        sel = model == m
        res.append({"model": m, "n": int(sel.sum()), "p": float(Y[sel].mean()),
                    "by_q": {f"{q:.4f}": survival(H[sel], Y[sel], q) for q in qs}})
    return res


def first_reversal(d):
    H, Y, model = d["H"], d["Y"], d["model"]
    names = [m for m in sorted(set(model.tolist())) if (model == m).sum() >= d["min_traj"]]
    true_p = np.array([Y[model == m].mean() for m in names])
    out = {}
    for policy in ("p_cc", "p_fail"):
        found = None
        for q in FINE_Q[1:]:
            obs = np.array([survival(H[model == m], Y[model == m], q)[policy] for m in names])
            dt = np.sign(true_p[:, None] - true_p[None, :])
            do = np.sign(obs[:, None] - obs[None, :])
            rev = int(np.triu((dt != 0) & (do != 0) & (dt != do), 1).sum())
            if rev > 0:
                found = {"q": float(q), "reversals": rev,
                         "m_corpus": survival(H, Y, q)["invalid_frac_m"]}
                break
        out[policy] = found
    srt = np.sort(true_p)
    gaps = np.diff(srt)
    out["n_models"] = len(names)
    out["median_adjacent_gap_pp"] = float(np.median(gaps) * 100)
    return out


# --------------------------------------------------------------------------
# 6. observed container failures (SWE early_exit) as real censoring
# --------------------------------------------------------------------------

def hajek_km(H, Y, E, strata=None):
    hmax = int(H.max())
    C = ~E
    if strata is None:
        G = km_censoring_survival(H, E, hmax)
        with np.errstate(divide="ignore"):
            w = np.where(C, 1.0 / G[H], 0.0)
    else:
        w = np.zeros(len(H))
        for s in np.unique(strata):
            sel = strata == s
            G = km_censoring_survival(H[sel], E[sel], hmax)
            with np.errstate(divide="ignore"):
                w[sel] = np.where(C[sel], 1.0 / G[H[sel]], 0.0)
    return float((w * Y).sum() / w.sum())


def observed_censoring(d):
    H, Y, E, model, task = d["H"], d["Y"], d["exit"] == "early_exit", d["model"], d["task"]
    N, M = len(Y), int(E.sum())
    S = Y[~E].sum()
    res = {
        "status": "early_exit",
        "definition": ("set by SWE-agent v0.7 swe_env.step() only when the container "
                       "runtime raises (RuntimeError, BrokenPipeError, or a failed "
                       "interrupt after a timeout), followed by a container reset"),
        "N": N, "M": M, "M_share": M / N,
        "resolved_among_M": int(Y[E].sum()),
        "fail_policy_pct": float(Y.mean() * 100),
        "drop_policy_pct": float(S / (N - M) * 100),
        "bounds_pct": [float(S / N * 100), float((S + M) / N * 100)],
        "hajek_km_pct": hajek_km(H, Y, E) * 100,
        "hajek_km_by_model_pct": hajek_km(H, Y, E, strata=model) * 100,
        "qhat_constant": float(M / H.sum()),
        "mean_H_early_exit": float(H[E].mean()),
    }
    # empirical discrete hazard by step band: events / run-steps at risk
    bands = [(1, 10), (11, 25), (26, 50), (51, 100), (101, 10**6)]
    haz = []
    for lo, hi in bands:
        exposure = np.clip(np.minimum(H, hi) - lo + 1, 0, None).sum()
        ev = (E & (H >= lo) & (H <= hi)).sum()
        haz.append({"band": f"{lo}-{'' if hi > 10**5 else hi}", "events": int(ev),
                    "run_steps": int(exposure),
                    "hazard_pct": float(ev / exposure * 100) if exposure else None})
    res["hazard_by_band"] = haz
    res["by_model"] = []
    for m in sorted(set(model.tolist())):
        sel = model == m
        res["by_model"].append({"model": m, "n": int(sel.sum()), "M": int(E[sel].sum()),
                                "qhat": float(E[sel].sum() / H[sel].sum())})
    # cluster bootstrap over tasks for the KM-weighted estimate
    rng = np.random.default_rng(REVISION_SEED + 7)
    uniq, inv = np.unique(task, return_inverse=True)
    idx_by_task = np.split(np.argsort(inv, kind="stable"),
                           np.cumsum(np.bincount(inv))[:-1])
    boots = np.empty(N_BOOT)
    for b in range(N_BOOT):
        pick = rng.integers(0, len(uniq), len(uniq))
        idx = np.concatenate([idx_by_task[i] for i in pick])
        boots[b] = hajek_km(H[idx], Y[idx], E[idx], strata=model[idx]) * 100
    res["hajek_km_by_model_ci95_pct"] = [float(np.percentile(boots, 2.5)),
                                         float(np.percentile(boots, 97.5))]
    # semi-synthetic results recomputed on the population without early_exit rows
    keep = ~E
    res["semi_synthetic_without_early_exit"] = {
        f"{q:.4f}": {k: survival(H[keep], Y[keep], q)[k]
                     for k in ("p", "bias_cc_pp", "bias_fail_pp")}
        for q in (0.01, 0.02)}
    return res


# Definition 1 applied to SWE-agent's exit statuses (semantics from the
# SWE-agent v0.6.1/v0.7.0 source: exit_context and exit_cost are budget
# exhaustion, exit_format is repeated malformed agent output, early_exit is a
# container runtime error).
EXIT_CLASS = {
    "submitted": "outcome (agent submitted)",
    "submitted_no_patch": "outcome (agent submitted, empty patch)",
    "submitted (exit_context)": "outcome (context exhausted, auto-submitted)",
    "exit_context": "outcome (context exhausted)",
    "submitted (exit_cost)": "outcome (cost budget, auto-submitted)",
    "exit_cost": "outcome (cost budget)",
    "submitted (exit_format)": "outcome (malformed output, auto-submitted)",
    "exit_format": "outcome (malformed output)",
    "early_exit": "unattributable (container runtime error)",
}


def exit_classification(d):
    rows = []
    for st in sorted(set(d["exit"].tolist()), key=lambda s: -(d["exit"] == s).sum()):
        sel = d["exit"] == st
        rows.append({"exit_status": st, "n": int(sel.sum()),
                     "resolve_rate": float(d["Y"][sel].mean()),
                     "class": EXIT_CLASS.get(st, "UNCLASSIFIED")})
    assert all(r["class"] != "UNCLASSIFIED" for r in rows)
    return rows


def make_horizon_figure(corpora):
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["pdf.fonttype"] = 42
    matplotlib.rcParams["ps.fonttype"] = 42
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(3.4, 1.55), sharey=True)
    for ax, d, title in zip(axes, corpora, ("SWE-agent", "$\\tau$-bench")):
        for y, col, lab in ((1, "#1e8449", "success"), (0, "#c0392b", "failure")):
            h = np.sort(d["H"][d["Y"] == y])
            xs = np.arange(1, h.max() + 1)
            ax.step(xs, 1 - np.searchsorted(h, xs, side="right") / len(h), where="post",
                    color=col, lw=1.0, label=lab)
        ax.set_xscale("log")
        ax.set_title(title, fontsize=7, pad=2)
        ax.set_xlabel("horizon $h$ (agent steps)", fontsize=6.5)
        ax.tick_params(labelsize=6)
        ax.grid(alpha=0.25, lw=0.4)
    axes[0].set_ylabel("$\\Pr(H>h\\mid Y)$", fontsize=6.5)
    axes[0].legend(fontsize=5.8, frameon=False, loc="lower left")
    fig.tight_layout(pad=0.25, w_pad=0.6)
    out = FIG_DIR / "fig2_horizon_survival.pdf"
    fig.savefig(out, bbox_inches="tight")
    fig.savefig(out.with_suffix(".png"), dpi=200, bbox_inches="tight")
    print(f"wrote {out}")


# --------------------------------------------------------------------------
# 7. figure
# --------------------------------------------------------------------------

def make_figure(swe_an, tau_an, surv, models):
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["pdf.fonttype"] = 42
    matplotlib.rcParams["ps.fonttype"] = 42
    import matplotlib.pyplot as plt

    DROP_C, FAIL_C, HT_C = "#c0392b", "#2471a3", "#1e8449"

    def panel(ax, a, title):
        an, mc = a["analytic"], a["monte_carlo"]
        q = np.array([r["q"] for r in an]) * 100
        pt = an[0]["p_true"] * 100
        ax.axhline(pt, color="black", lw=1.1, zorder=3, label="True reliability")
        ax.plot(q, [r["p_drop"] * 100 for r in an], "o-", color=DROP_C, lw=1.2, ms=3,
                zorder=4, label="Drop invalid")
        ax.plot(q, [r["p_fail"] * 100 for r in an], "s-", color=FAIL_C, lw=1.2, ms=3,
                zorder=4, label="Invalid as failure")
        mq = np.array([0.0] + [m["q"] for m in mc]) * 100
        ax.plot(mq, [pt] + [m["ht"]["mean"] * 100 for m in mc], "^--", color=HT_C,
                lw=1.1, ms=3, zorder=5, label="IPCW (HT)")
        ax.fill_between(mq, [pt] + [m["ht"]["ci95_lo_pp"] for m in mc],
                        [pt] + [m["ht"]["ci95_hi_pp"] for m in mc],
                        color=HT_C, alpha=0.18, lw=0, zorder=2)
        ax.set_title(title, fontsize=7.4, pad=3)
        ax.set_xlabel("Per-step hazard $q$ (%)", fontsize=7.2)
        ax.tick_params(labelsize=6.4)
        ax.grid(alpha=0.25, lw=0.4)
        ax.set_xlim(-0.05, 2.05)

    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.1),
                             gridspec_kw={"width_ratios": [1, 1, 0.82]})
    r_s = surv["SWE-agent"][-1]["rho"]
    r_t = surv["tau-bench"][-1]["rho"]
    panel(axes[0], swe_an, f"(a) SWE-agent, $\\rho_{{2\\%}}$={r_s:.2f}")
    panel(axes[1], tau_an, f"(b) $\\tau$-bench, $\\rho_{{2\\%}}$={r_t:.3f}")
    axes[0].set_ylabel("Reported success rate (%)", fontsize=7.2)
    axes[0].legend(fontsize=5.8, frameon=False, loc="lower left",
                   borderaxespad=0.3, handlelength=1.7)

    ax = axes[2]
    key = "0.0100"
    lim = (0.66, 1.0)
    ax.plot(lim, lim, color="0.5", lw=0.8, ls=":", zorder=1)
    for mrow in models["tau-bench"]:
        r = mrow["by_q"][key]
        ax.scatter(r["pbar0"], r["pbar1"], s=9, color="#7d3c98", alpha=0.75, lw=0, zorder=3)
    for mrow in models["SWE-agent"]:
        r = mrow["by_q"][key]
        ax.scatter(r["pbar0"], r["pbar1"], s=14, marker="D", color="#d35400", lw=0, zorder=4)
    for name, col, mk in (("SWE-agent", "#d35400", "D"), ("tau-bench", "#7d3c98", "o")):
        pts = surv[name]
        ax.plot([r["pbar0"] for r in pts], [r["pbar1"] for r in pts], "-", color=col,
                lw=0.9, alpha=0.8, zorder=2)
    ax.scatter([], [], s=9, color="#7d3c98", label="$\\tau$-bench models")
    ax.scatter([], [], s=14, marker="D", color="#d35400", label="SWE-agent models")
    ax.text(0.675, 0.985, "drop overstates\n($\\rho>1$)", fontsize=5.6, va="top")
    ax.text(0.99, 0.672, "drop understates", fontsize=5.6, ha="right")
    ax.text(0.668, 0.80, "SWE corpus", fontsize=5.4, color="#d35400", rotation=38)
    ax.text(0.80, 0.735, "$\\tau$ corpus", fontsize=5.4, color="#7d3c98", rotation=45)
    ax.set_xlim(*lim)
    ax.set_ylim(*lim)
    ax.set_aspect("equal")
    ax.set_xlabel("$\\bar\\pi_0$ (mean survival, failures)", fontsize=7.2)
    ax.set_ylabel("$\\bar\\pi_1$ (successes)", fontsize=7.2, labelpad=1)
    ax.set_title("(c) Survival plane, $q$=1%", fontsize=7.4, pad=3)
    ax.tick_params(labelsize=6.4)
    ax.grid(alpha=0.25, lw=0.4)
    ax.legend(fontsize=5.6, frameon=False, loc="lower right",
              bbox_to_anchor=(1.0, 0.08), handletextpad=0.2)
    fig.tight_layout(pad=0.3, w_pad=0.9)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    out = FIG_DIR / "fig1_censoring_bias.pdf"
    fig.savefig(out, bbox_inches="tight")
    fig.savefig(out.with_suffix(".png"), dpi=200, bbox_inches="tight")
    print(f"wrote {out}")


# --------------------------------------------------------------------------

def main() -> int:
    corpora = [load_swe(), load_tau()]
    payload = {"kind": "censoring_revision_analysis",
               "generated_at": datetime.now(timezone.utc).isoformat(),
               "note": "added in revision after review; predeclared analyses unchanged",
               "revision_seed": REVISION_SEED}
    surv, models = {}, {}
    for d in corpora:
        name, H, Y = d["name"], d["H"], d["Y"]
        print(f"\n===== {name}  N={len(Y)}  p={Y.mean():.4f}")
        rows = [survival(H, Y, q) for q in Q_GRID[1:]]
        surv[name] = [survival(H, Y, 0.0)] + rows
        for r in rows:
            print(f"q={r['q']:.4f} pbar1={r['pbar1']:.4f} pbar0={r['pbar0']:.4f} "
                  f"rho={r['rho']:.4f} m={r['invalid_frac_m']:.3f} "
                  f"cc={r['bias_cc_pp']:+.2f} fail={r['bias_fail_pp']:+.2f} "
                  f"log_rho={r['log_rho']:.4f} first_order={r['first_order_log_rho']:.4f} "
                  f"id_err={r['identity_max_abs_err']:.1e}")
        dom = dominance(H, Y)
        print("dominance:", dom)
        rr = [rerun(H, Y, d["cell"], q) for q in Q_GRID[1:]]
        for r in rr:
            print(f"rerun q={r['q']:.4f} cc={r['bias_cc_pp']:+.3f} within={r['within_pp']:+.3f} "
                  f"between={r['between_pp']:+.3f} rerun={r['bias_rerun_pp']:+.3f} "
                  f"removed={r['share_of_cc_bias_removed_by_rerun']:.2f} "
                  f"attempts={r['expected_attempts_per_task']:.3f} "
                  f"singletons={r['share_runs_in_singleton_cells']:.3f}")
        crit = critical(H, Y)
        print("critical:", crit)
        models[name] = per_model(d, [0.01, 0.02])
        below = [m["model"] for m in models[name] if m["by_q"]["0.0100"]["rho"] < 1]
        print(f"models with rho<1 at q=1%: {len(below)}/{len(models[name])} {below}")
        rev = first_reversal(d)
        print("first reversal:", rev)
        dep = []
        scen = [(q, False) for q in (0.005, 0.01, 0.02)] + [(q, True) for q in (0.005, 0.01)]
        for i, (q0, sd) in enumerate(scen):
            r = deployable_mc(H, Y, q0, sd, N_REPLICATES, REVISION_SEED + 100 * i
                              + (0 if name == "SWE-agent" else 50))
            dep.append(r)
            print(f"deployable q0={q0} {r['hazard'][:8]}: " + " ".join(
                f"{k}={r[k]['bias_pp']:+.3f}({r[k]['sd_pp']:.3f})"
                for k in ("ht_known", "hajek_km", "ht_km", "hajek_param")))
        caps = [hard_cap(H, Y, K) for K in (25, 50)]
        for c in caps:
            print(f"hard cap K={c['K']}: invalid={c['invalid_frac']:.3f} drop={c['drop_pct']:.2f} "
                  f"km={c['km_pct']:.2f} fail={c['fail_pct']:.2f} bounds={c['bounds_pct']}")
        payload[name] = {"hard_cap": caps,
                         "survival": surv[name], "dominance": dom, "rerun": rr,
                         "critical": crit, "models": models[name],
                         "first_reversal": rev, "deployable_ipcw": dep,
                         "models_rho_below_1_at_q1pct": below}
        if name == "SWE-agent":
            obs = observed_censoring(d)
            payload[name]["observed_early_exit"] = obs
            payload[name]["exit_classification"] = exit_classification(d)
            for r in payload[name]["exit_classification"]:
                print(f"  exit {r['exit_status']:26} n={r['n']:6d} "
                      f"resolve={r['resolve_rate']:.3f} {r['class']}")
            print("observed early_exit:", json.dumps(obs, indent=1))
        else:
            payload[name]["finish_reasons"] = {k: int(v) for k, v in
                                               zip(*np.unique(d["exit"], return_counts=True))}

    (OUT_DIR / "revision_analysis.json").write_text(json.dumps(payload, indent=2),
                                                    encoding="utf-8")
    print(f"\nwrote {OUT_DIR / 'revision_analysis.json'}")

    swe_an = json.loads((OUT_DIR / "analysis.json").read_text(encoding="utf-8"))
    tau_an = json.loads((OUT_DIR / "tau_analysis.json").read_text(encoding="utf-8"))
    make_figure(swe_an, tau_an, surv, models)
    make_horizon_figure(corpora)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
