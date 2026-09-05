"""Analytic censoring bias, IPCW Monte Carlo, model-level ranking, and figures.

Everything here is computed from results/censoring/trajectory_summary.parquet.
No API calls and no model inference.

    uv run python scripts/censoring/analyze.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "results" / "censoring"
FIG_DIR = REPO_ROOT / "tas_overleaf" / "figures"

# ---- PREDECLARED CONSTANTS (fixed before any censoring curve was examined) ----
Q_GRID = [0.0000, 0.0010, 0.0025, 0.0050, 0.0100, 0.0200]
MASTER_SEED = 20260905
N_REPLICATES = 200
MIN_TRAJ_PER_MODEL = 500
HORIZON_BINS = [(1, 25), (26, 50), (51, 75), (76, 10**9)]
STRESS_BREAKPOINT = 25  # steps; hazard doubles beyond this in the stress test


def load():
    tbl = pq.read_table(OUT_DIR / "trajectory_summary.parquet")
    H = np.asarray(tbl.column("step_count")).astype(np.int64)
    Y = np.asarray(tbl.column("target")).astype(np.float64)
    model = np.asarray(tbl.column("model_name"))
    inst = np.asarray(tbl.column("instance_id"))
    # Primary population: every row with a defined target label. The single
    # H=0 row (context exhausted before the agent emitted a turn) is a
    # legitimately labelled execution and is RETAINED: under pi=s^H it has
    # observation probability s^0=1, so it is simply never censored. Excluding
    # it would be filtering on an inconvenience rather than a principle.
    keep = np.ones(len(H), dtype=bool)
    return H[keep], Y[keep], model[keep], inst[keep]


def analytic(H, Y, q, weights=None):
    """Induced estimands under pi(H)=s^H, computed exactly (no simulation).

    `p_drop` is the complete-case *induced population estimand*
    E[Y s^H]/E[s^H] = P(Y=1 | C=1) -- the probability limit of the
    complete-case ratio estimator, NOT its exact finite-sample expectation
    (the expectation of a ratio is not the ratio of expectations).

    `p_fail` IS the exact expectation of (1/n) sum_i C_i Y_i, since that
    estimator is linear in C.

    `weights` optionally reweights the finite corpus (used for the
    task-balanced robustness check).
    """
    s = 1.0 - q
    w = s ** H  # observation probability pi_i
    u = np.ones_like(Y) if weights is None else weights
    u = u / u.sum()
    p = float((u * Y).sum())
    p_drop = float((u * Y * w).sum() / (u * w).sum())
    p_fail = float((u * Y * w).sum())
    cov = float((u * Y * w).sum() - p * (u * w).sum())
    return {
        "q": q,
        "p_true": float(p),
        "p_drop": p_drop,
        "p_fail": p_fail,
        "bias_drop_pp": (p_drop - p) * 100,
        "bias_fail_pp": (p_fail - p) * 100,
        "rel_bias_drop_pct": (p_drop - p) / p * 100,
        "rel_bias_fail_pct": (p_fail - p) / p * 100,
        "cov_Y_sH": cov,
        "E_sH": float((u * w).sum()),
        "cov_over_EsH_pp": (cov / (u * w).sum()) * 100,
        "expected_retained_frac": float((u * w).sum()),
        # Assumption-free worst-case identification interval for p, using the
        # EXPECTED censored count. S/N <= p <= (S+M)/N with S = observed
        # successes, M = censored count, N = initiated runs.
        "bound_lo": p_fail,
        "bound_hi": float(p_fail + (1.0 - (u * w).sum())),
        "bound_width": float(1.0 - (u * w).sum()),
    }


def monte_carlo(H, Y, q, n_rep, seed):
    """Simulate Bernoulli terminal censoring and evaluate four estimators."""
    rng = np.random.default_rng(seed)
    pi = (1.0 - q) ** H
    n = len(Y)
    est = {k: np.empty(n_rep) for k in ("drop", "fail", "ht", "hajek")}
    retained = np.empty(n_rep)
    for r in range(n_rep):
        C = rng.random(n) < pi
        retained[r] = C.mean()
        nc = C.sum()
        est["drop"][r] = Y[C].mean() if nc else np.nan
        est["fail"][r] = (Y * C).mean()
        est["ht"][r] = (C * Y / pi).sum() / n
        est["hajek"][r] = (C * Y / pi).sum() / (C / pi).sum()
    p = Y.mean()
    out = {"q": q, "n_replicates": n_rep, "p_true": float(p),
           "mean_retained_frac": float(retained.mean())}
    for k, v in est.items():
        out[k] = {
            "mean": float(np.nanmean(v)),
            "bias_pp": float(np.nanmean(v) - p) * 100,
            "sd_pp": float(np.nanstd(v, ddof=1)) * 100,
            "rmse_pp": float(np.sqrt(np.nanmean((v - p) ** 2))) * 100,
            "ci95_lo_pp": float(np.nanpercentile(v, 2.5)) * 100,
            "ci95_hi_pp": float(np.nanpercentile(v, 97.5)) * 100,
        }
    return out


def stress_test(H, Y, q0, n_rep, seed):
    """Censor under a step-dependent hazard but weight as if it were constant."""
    rng = np.random.default_rng(seed)
    # True survival: hazard q0 for t<=B, 2*q0 beyond.
    b = np.minimum(H, STRESS_BREAKPOINT)
    extra = np.maximum(H - STRESS_BREAKPOINT, 0)
    pi_true = (1 - q0) ** b * (1 - 2 * q0) ** extra
    pi_assumed = (1 - q0) ** H  # misspecified constant-hazard weights
    n = len(Y)
    p = Y.mean()
    ht = np.empty(n_rep)
    hj = np.empty(n_rep)
    for r in range(n_rep):
        C = rng.random(n) < pi_true
        ht[r] = (C * Y / pi_assumed).sum() / n
        hj[r] = (C * Y / pi_assumed).sum() / (C / pi_assumed).sum()
    return {
        "q0": q0,
        "breakpoint_steps": STRESS_BREAKPOINT,
        "true_hazard": f"q0 for t<={STRESS_BREAKPOINT}, 2*q0 beyond",
        "assumed_hazard": "constant q0",
        "p_true": float(p),
        "ht_mean": float(ht.mean()),
        "ht_bias_pp": float(ht.mean() - p) * 100,
        "hajek_mean": float(hj.mean()),
        "hajek_bias_pp": float(hj.mean() - p) * 100,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    H, Y, model, inst = load()
    n = len(Y)
    p = float(Y.mean())
    print(f"population n={n}  p_true={p:.6f}  meanH={H.mean():.2f}")
    print(f"  meanH|Y=1 {H[Y == 1].mean():.2f}   meanH|Y=0 {H[Y == 0].mean():.2f}")
    print(f"  H=0 rows retained: {(H == 0).sum()}")

    # ---------------- analytic (primary result) ----------------
    analytic_rows = [analytic(H, Y, q) for q in Q_GRID]
    print(f"\n{'q':>7} {'p_drop':>9} {'p_fail':>9} {'bias_drop':>10} {'bias_fail':>10} "
          f"{'retain':>7} {'bounds':>16}")
    for r in analytic_rows:
        print(f"{r['q']:7.4f} {r['p_drop']:9.5f} {r['p_fail']:9.5f} "
              f"{r['bias_drop_pp']:+10.3f} {r['bias_fail_pp']:+10.3f} "
              f"{r['expected_retained_frac']:7.3f} "
              f"[{r['bound_lo']:.4f},{r['bound_hi']:.4f}]")

    # ---------------- task-balanced robustness ----------------
    # Each benchmark instance_id gets equal total weight, so repeated tasks and
    # unequal per-model coverage cannot drive the estimand by count alone.
    uniq, inv, counts = np.unique(inst, return_inverse=True, return_counts=True)
    task_w = 1.0 / counts[inv]
    task_rows = [analytic(H, Y, q, weights=task_w) for q in Q_GRID]
    print(f"\ntask-balanced ({len(uniq)} unique instance_ids):")
    for r in task_rows:
        print(f"{r['q']:7.4f} p_true={r['p_true']:.5f} "
              f"bias_drop={r['bias_drop_pp']:+.3f} bias_fail={r['bias_fail_pp']:+.3f}")

    # ---------------- Monte Carlo IPCW validation ----------------
    mc_rows = []
    for i, q in enumerate(Q_GRID):
        if q == 0.0:
            continue
        mc_rows.append(monte_carlo(H, Y, q, N_REPLICATES, MASTER_SEED + i))
        m = mc_rows[-1]
        print(f"\nq={q}: retained={m['mean_retained_frac']:.3f}")
        for k in ("drop", "fail", "ht", "hajek"):
            print(f"   {k:6} mean={m[k]['mean']:.5f} bias={m[k]['bias_pp']:+.3f}pp "
                  f"sd={m[k]['sd_pp']:.3f}pp rmse={m[k]['rmse_pp']:.3f}pp")

    # ---------------- model-level ----------------
    models = sorted(set(model.tolist()))
    eligible = [m for m in models if (model == m).sum() >= MIN_TRAJ_PER_MODEL]
    model_rows = []
    for m in eligible:
        sel = model == m
        Hm, Ym = H[sel], Y[sel]
        row = {
            "model_name": m,
            "n": int(sel.sum()),
            "p_true": float(Ym.mean()),
            "mean_H": float(Hm.mean()),
            "median_H": float(np.median(Hm)),
            "mean_H_success": float(Hm[Ym == 1].mean()) if (Ym == 1).any() else None,
            "mean_H_failure": float(Hm[Ym == 0].mean()) if (Ym == 0).any() else None,
            "by_q": {},
        }
        for q in Q_GRID:
            a = analytic(Hm, Ym, q)
            row["by_q"][f"{q:.4f}"] = {
                "p_true": a["p_true"], "p_drop": a["p_drop"], "p_fail": a["p_fail"]
            }
        model_rows.append(row)

    # ranking analysis across eligible models
    def ranking(vals):
        order = sorted(range(len(vals)), key=lambda i: -vals[i])
        return order

    true_vals = [r["p_true"] for r in model_rows]
    true_order = ranking(true_vals)
    n_pairs = len(model_rows) * (len(model_rows) - 1) // 2
    ranking_rows = []
    for q in Q_GRID:
        rep = {}
        for policy in ("p_drop", "p_fail"):
            vals = [r["by_q"][f"{q:.4f}"][policy] for r in model_rows]
            order = ranking(vals)
            reversals = 0
            for i in range(len(model_rows)):
                for j in range(i + 1, len(model_rows)):
                    t = np.sign(true_vals[i] - true_vals[j])
                    o = np.sign(vals[i] - vals[j])
                    if t != 0 and o != 0 and t != o:
                        reversals += 1
            # Spearman on ranks (small n, computed directly)
            def ranks(v):
                idx = sorted(range(len(v)), key=lambda i: v[i])
                rk = [0] * len(v)
                for pos, i in enumerate(idx):
                    rk[i] = pos + 1
                return rk
            rt, ro = ranks(true_vals), ranks(vals)
            dsq = sum((a - b) ** 2 for a, b in zip(rt, ro))
            k = len(vals)
            rho = 1 - 6 * dsq / (k * (k * k - 1)) if k > 1 else 1.0
            rep[policy] = {
                "order_same_as_true": order == true_order,
                "pairwise_reversals": reversals,
                "spearman_rho": float(rho),
            }
        rep["q"] = q
        rep["n_eligible_models"] = len(model_rows)
        rep["n_model_pairs"] = n_pairs
        ranking_rows.append(rep)

    # ---------------- horizon strata ----------------
    strata = []
    for lo, hi in HORIZON_BINS:
        sel = (H >= lo) & (H <= hi)
        if not sel.any():
            continue
        s = {"bin": f"{lo}-{'inf' if hi > 10**8 else hi}", "n": int(sel.sum()),
             "share": float(sel.mean()), "p_true": float(Y[sel].mean()),
             "mean_H": float(H[sel].mean())}
        for q in Q_GRID:
            if q > 0:
                s[f"retain_q{q}"] = float(((1 - q) ** H[sel]).mean())
        strata.append(s)

    # ---------------- misspecification stress test ----------------
    stress = [stress_test(H, Y, q, N_REPLICATES, MASTER_SEED + 500 + i)
              for i, q in enumerate([0.0050, 0.0100])]

    payload = {
        "kind": "censoring_analysis",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "predeclared": {
            "q_grid": Q_GRID,
            "master_seed": MASTER_SEED,
            "n_replicates": N_REPLICATES,
            "min_trajectories_per_model": MIN_TRAJ_PER_MODEL,
            "horizon_bins": [list(b) for b in HORIZON_BINS],
            "step_count_definition": 'H = count of trajectory messages with role=="ai"',
        },
        "population": {
            "n": n, "p_true": p,
            "mean_H": float(H.mean()),
            "mean_H_success": float(H[Y == 1].mean()),
            "mean_H_failure": float(H[Y == 0].mean()),
            "median_H_success": float(np.median(H[Y == 1])),
            "median_H_failure": float(np.median(H[Y == 0])),
            "max_H": int(H.max()),
            "n_zero_step_rows": int((H == 0).sum()),
            "population_rule": (
                "all rows with a defined target label; the single H=0 row is "
                "retained because pi=s^0=1 makes it never censored"
            ),
        },
        "analytic": analytic_rows,
        "task_balanced": task_rows,
        "n_unique_instances": int(len(uniq)),
        "monte_carlo": mc_rows,
        "models": model_rows,
        "ranking": ranking_rows,
        "horizon_strata": strata,
        "stress_test": stress,
    }
    (OUT_DIR / "analysis.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT_DIR/'analysis.json'}")

    make_figure(analytic_rows, mc_rows, payload)
    return 0


def make_figure(analytic_rows, mc_rows, payload):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    q = np.array([r["q"] for r in analytic_rows]) * 100
    p_true = analytic_rows[0]["p_true"] * 100
    drop = np.array([r["p_drop"] for r in analytic_rows]) * 100
    fail = np.array([r["p_fail"] for r in analytic_rows]) * 100

    mcq = np.array([0.0] + [m["q"] for m in mc_rows]) * 100
    ht = np.array([p_true] + [m["ht"]["mean"] * 100 for m in mc_rows])
    ht_lo = np.array([p_true] + [m["ht"]["ci95_lo_pp"] for m in mc_rows])
    ht_hi = np.array([p_true] + [m["ht"]["ci95_hi_pp"] for m in mc_rows])

    fig, ax = plt.subplots(figsize=(3.4, 2.5))
    ax.axhline(p_true, color="black", lw=1.2, ls="-", label="True reliability", zorder=3)
    ax.plot(q, drop, "o-", color="#c0392b", lw=1.3, ms=3.4,
            label="Drop invalid (complete case)", zorder=4)
    ax.plot(q, fail, "s-", color="#2471a3", lw=1.3, ms=3.4,
            label="Invalid as failure", zorder=4)
    ax.plot(mcq, ht, "^--", color="#1e8449", lw=1.2, ms=3.4,
            label="IPCW (Horvitz–Thompson)", zorder=5)
    ax.fill_between(mcq, ht_lo, ht_hi, color="#1e8449", alpha=0.18, lw=0, zorder=2)

    ax.set_xlabel("Per-step infrastructure hazard $q$ (%)", fontsize=8)
    ax.set_ylabel("Reported success rate (%)", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.legend(fontsize=6.0, frameon=False, loc="upper left",
              borderaxespad=0.3, handlelength=1.8)
    ax.grid(alpha=0.25, lw=0.4)
    ax.set_xlim(-0.05, 2.05)
    fig.tight_layout(pad=0.25)
    out = FIG_DIR / "fig1_censoring_bias.pdf"
    fig.savefig(out, bbox_inches="tight")
    fig.savefig(out.with_suffix(".png"), dpi=200, bbox_inches="tight")
    print(f"wrote {out}")


if __name__ == "__main__":
    raise SystemExit(main())
