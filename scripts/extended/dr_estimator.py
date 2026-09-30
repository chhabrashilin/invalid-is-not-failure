"""Doubly robust (augmented IPCW) estimation of reliability from partial
trajectories (extended paper).

A censored agent run is not empty: its prefix up to the failure step is
observed. The discrete-time augmented IPCW estimator

  p_DR = N^-1 sum_i [ C_i Y_i / G(H_i)
                      + sum_{t <= V_i} (dN_i(t) - lambda(t)) mu(x_it) / G(t) ]

adds to Kaplan-Meier weighting an outcome model mu(x_it) = P(Y=1 | prefix
before step t, H >= t). dN_i(t) = 1 if run i was invalidated during step t,
lambda is the discrete censoring hazard and G(t) = prod_{s<=t} (1 - lambda(s)).
The estimator is consistent if either G or mu is correct, and a good mu
reduces variance. With mu = Y the bracket equals Y exactly (a telescoping
identity, checked below).

Prefix features at step t use only steps 1..t-1: elapsed steps, counts of
edit / create / run / navigation actions, whether any edit failed its syntax
check, whether the last observation showed an error, whether a clean run
followed the last edit, and the model.

    uv run python scripts/extended/dr_estimator.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "censoring"))
from revision_analysis import STRESS_BREAKPOINT, km_censoring_survival  # noqa: E402

OUT = REPO_ROOT / "results" / "extended"
SUMMARY = REPO_ROOT / "results" / "censoring" / "trajectory_summary.parquet"
SEED = 20260930
N_REP = 50
OTHER, NAV, EDIT, CREATE, RUN, SUBMIT = range(6)


# --------------------------------------------------------------------------
# data and prefix features
# --------------------------------------------------------------------------

def load():
    t = pq.read_table(SUMMARY)
    H = np.asarray(t.column("step_count")).astype(np.int64)
    Y = np.asarray(t.column("target")).astype(float)
    model = np.asarray(t.column("model_name")).astype(str)
    task = np.asarray(t.column("instance_id")).astype(str)
    exits = np.asarray(t.column("exit_status")).astype(str)
    z = np.load(OUT / "swe_prefix_records.npz")
    assert (z["lengths"] == H).all()
    return H, Y, model, task, exits, z["codes"], z["obs_err"], z["edit_fail"]


def build_features(H, model, codes, obs_err, edit_fail):
    """Feature row for every (run i, step t), t = 1..H_i, using steps < t."""
    n_steps = int(H.sum())
    run_of = np.repeat(np.arange(len(H)), H)
    start = np.repeat(np.cumsum(H) - H, H)
    t = np.arange(n_steps) - start + 1  # 1-based step index

    def run_exclusive_count(flag):
        """Count of flagged steps strictly before each step, within its run."""
        c = np.concatenate([[0], np.cumsum(flag.astype(np.int64))])
        return c[np.arange(n_steps)] - c[start]

    n_edit = run_exclusive_count(codes == EDIT)
    n_create = run_exclusive_count(codes == CREATE)
    n_run = run_exclusive_count(codes == RUN)
    n_nav = run_exclusive_count(codes == NAV)
    n_fail = run_exclusive_count(edit_fail == 1)
    prev = np.arange(n_steps) - 1
    first = t == 1
    last_err = np.where(first, 0, obs_err[np.maximum(prev, 0)])
    # clean run after the most recent edit, among steps < t
    idx = np.arange(n_steps)
    edit_pos = np.where(codes == EDIT, idx, -1)
    clean_pos = np.where((codes == RUN) & (obs_err == 0), idx, -1)
    last_edit = np.maximum.accumulate(edit_pos)
    last_clean = np.maximum.accumulate(clean_pos)
    le = np.where(first, -1, last_edit[np.maximum(prev, 0)])
    lc = np.where(first, -1, last_clean[np.maximum(prev, 0)])
    le = np.where(le >= start, le, -1)
    lc = np.where(lc >= start, lc, -1)
    verified_fix = (le >= 0) & (lc > le)
    n_err = run_exclusive_count(obs_err == 1)
    since_edit = np.where(le >= 0, idx - le, t)  # steps since last edit (or since start)
    ls = np.log1p(t - 1)
    any_edit = (n_edit > 0).astype(float)
    models = sorted(set(model.tolist()))
    dummies = [(model[run_of] == m).astype(float) for m in models[1:]]
    X = np.column_stack([
        np.ones(n_steps), ls, ls ** 2, np.log1p(n_edit), np.log1p(n_create),
        np.log1p(n_run), np.log1p(n_nav), any_edit, (n_fail > 0), last_err,
        verified_fix, np.log1p(n_err), np.log1p(since_edit), ls * any_edit,
        ls * verified_fix, *dummies]).astype(np.float64)
    names = ["const", "log_steps", "log_steps_sq", "log_edit", "log_create", "log_run",
             "log_nav", "any_edit", "any_edit_fail", "last_obs_err",
             "clean_run_after_edit", "log_obs_errors", "log_steps_since_edit",
             "log_steps_x_any_edit", "log_steps_x_clean_run",
             *[f"model={m}" for m in models[1:]]]
    return X, run_of, t, start, names


# --------------------------------------------------------------------------
# weighted logistic regression (IRLS)
# --------------------------------------------------------------------------

def fit_logistic(X, y, w, iters=25, ridge=1e-6, beta0=None):
    beta = np.zeros(X.shape[1]) if beta0 is None else beta0.copy()
    for _ in range(iters):
        eta = np.clip(X @ beta, -30, 30)
        mu = 1 / (1 + np.exp(-eta))
        W = w * mu * (1 - mu)
        grad = X.T @ (w * (y - mu)) - ridge * beta
        Hs = (X * W[:, None]).T @ X + ridge * np.eye(X.shape[1])
        step = np.linalg.solve(Hs, grad)
        beta += step
        if np.abs(step).max() < 1e-8:
            break
    return beta


def predict(X, beta):
    return 1 / (1 + np.exp(-np.clip(X @ beta, -30, 30)))


def auc(score, y):
    order = np.argsort(score)
    r = np.empty(len(score))
    r[order] = np.arange(1, len(score) + 1)
    n1 = y.sum()
    n0 = len(y) - n1
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


# --------------------------------------------------------------------------
# censoring simulation and estimators
# --------------------------------------------------------------------------

def draw_T(rng, n, q0, stepdep):
    T = rng.geometric(q0, size=n)
    if stepdep:
        late = T > STRESS_BREAKPOINT
        T[late] = STRESS_BREAKPOINT + rng.geometric(min(2 * q0, 1.0), size=late.sum())
    return T


def hazard_from_G(G):
    lam = np.zeros_like(G)
    prevG = np.concatenate([[1.0], G[:-1]])
    lam[1:] = 1 - G[1:] / np.where(prevG[1:] > 0, prevG[1:], 1)
    return lam


def dr_estimate(Y, H, C, V, T, G, mu_rows, run_of, t_rows):
    """Augmented IPCW with censoring survival G (array over steps) and outcome
    predictions mu_rows for every (i, t) feature row."""
    N = len(Y)
    lam = hazard_from_G(G)
    with np.errstate(divide="ignore", invalid="ignore"):
        ipcw = np.where(C, Y / G[H], 0.0)
    at_risk = t_rows <= V[run_of]
    dN = (~C[run_of]) & (t_rows == T[run_of])
    # G(t) = 0 only when every run at risk at t was invalidated there, in which
    # case dN - lambda = 0 for all of them and the term is 0.
    Gsafe = np.where(G > 0, G, np.inf)
    aug_rows = np.where(at_risk, (dN - lam[t_rows]) * mu_rows / Gsafe[t_rows], 0.0)
    aug = np.bincount(run_of, weights=aug_rows, minlength=N)
    with np.errstate(divide="ignore", invalid="ignore"):
        hajek = np.where(C, Y / G[H], 0.0).sum() / np.where(C, 1 / G[H], 0.0).sum()
    return float((ipcw + aug).mean()), float(hajek)


TRAIN_FRAC = 0.25
_train_rng = np.random.default_rng(SEED + 7)
_beta_warm = None


def fit_outcome_model(X, Y, H, C, G, run_of, t_rows, folds_run, fold):
    """Fit mu on completed runs of the other fold with weights G(t-1)/G(H),
    on a random quarter of their step rows (warm-started IRLS)."""
    Gprev = np.concatenate([[1.0], G])  # Gprev[t] = G(t-1)
    rows = np.flatnonzero(C[run_of] & (folds_run[run_of] != fold))
    rows = rows[_train_rng.random(len(rows)) < TRAIN_FRAC]
    w = Gprev[t_rows[rows]] / G[H[run_of[rows]]]
    return fit_logistic(X[rows], Y[run_of[rows]], w, beta0=_beta_warm)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    H, Y, model, task, exits, codes, obs_err, edit_fail = load()
    X, run_of, t_rows, start, names = build_features(H, model, codes, obs_err, edit_fail)
    N = len(Y)
    p = Y.mean()
    hmax = int(H.max()) + 1
    print(f"N={N} p={p:.4f} feature rows={len(X)}")

    # task-level 2-fold split for cross-fitting
    uniq, inv = np.unique(task, return_inverse=True)
    rng0 = np.random.default_rng(SEED)
    fold_task = rng0.integers(0, 2, len(uniq))
    folds_run = fold_task[inv]

    # identity check: with mu = Y the DR bracket equals Y for every run
    rng = np.random.default_rng(SEED + 1)
    T = draw_T(rng, N, 0.01, False)
    C = T > H
    V = np.where(C, H, T)
    G = km_censoring_survival(V, ~C, hmax)
    psi, _ = dr_estimate(Y, H, C, V, T, G, Y[run_of], run_of, t_rows)
    ident_err = abs(psi - p)
    print(f"identity check |p_DR(mu=Y) - p| = {ident_err:.2e}")

    # predictive power of prefixes (full data, no censoring): AUC by step
    global _beta_warm
    beta_full = fit_logistic(X, Y[run_of], np.ones(len(X)))
    _beta_warm = beta_full
    mu_full = predict(X, beta_full)
    auc_by_t = {}
    for tt in (1, 5, 10, 20, 40):
        sel = t_rows == tt
        if sel.sum() > 100 and 0 < Y[run_of[sel]].mean() < 1:
            auc_by_t[tt] = auc(mu_full[sel], Y[run_of[sel]])
    print("AUC of prefix model by step:", {k: round(v, 3) for k, v in auc_by_t.items()})

    scenarios = [(0.01, False), (0.02, False), (0.01, True)]
    results = []
    for si, (q0, stepdep) in enumerate(scenarios):
        est = {k: [] for k in ("km_hajek", "dr_km", "dr_km_null", "param_hajek",
                               "dr_param")}
        rng = np.random.default_rng(SEED + 100 + si)
        for r in range(N_REP):
            T = draw_T(rng, N, q0, stepdep)
            C = T > H
            V = np.where(C, H, T)
            G_km = km_censoring_survival(V, ~C, hmax)
            qhat = (~C).sum() / V.sum()
            G_par = (1 - qhat) ** np.arange(hmax + 1)
            for Gname, G in (("km", G_km), ("param", G_par)):
                mu_rows = np.empty(len(X))
                for fold in (0, 1):
                    beta = fit_outcome_model(X, Y, H, C, G, run_of, t_rows, folds_run, fold)
                    sel = folds_run[run_of] == fold
                    mu_rows[sel] = predict(X[sel], beta)
                psi, hajek = dr_estimate(Y, H, C, V, T, G, mu_rows, run_of, t_rows)
                if Gname == "km":
                    est["dr_km"].append(psi)
                    est["km_hajek"].append(hajek)
                    # deliberately wrong outcome model: constant 0.5
                    psi0, _ = dr_estimate(Y, H, C, V, T, G, np.full(len(X), 0.5),
                                          run_of, t_rows)
                    est["dr_km_null"].append(psi0)
                else:
                    est["dr_param"].append(psi)
                    est["param_hajek"].append(hajek)
            if (r + 1) % 25 == 0:
                print(f"  scenario {si} rep {r + 1}", flush=True)
        row = {"q0": q0, "hazard": "step-dependent" if stepdep else "constant",
               "n_rep": N_REP}
        for k, v in est.items():
            v = np.asarray(v)
            row[k] = {"bias_pp": float((v.mean() - p) * 100),
                      "sd_pp": float(v.std(ddof=1) * 100),
                      "rmse_pp": float(np.sqrt(((v - p) ** 2).mean()) * 100)}
        results.append(row)
        print(f"q0={q0} {row['hazard']}: " + "  ".join(
            f"{k}={row[k]['bias_pp']:+.3f}({row[k]['sd_pp']:.3f})" for k in est))

    # real censoring: SWE-agent early_exit runs, crash during their last step
    E = exits == "early_exit"
    Creal = ~E
    Vreal = H.copy()
    Treal = np.where(E, H, H + 10**6)
    G_real = km_censoring_survival(Vreal, E, hmax)
    mu_rows = np.empty(len(X))
    for fold in (0, 1):
        beta = fit_outcome_model(X, Y, H, Creal, G_real, run_of, t_rows, folds_run, fold)
        sel = folds_run[run_of] == fold
        mu_rows[sel] = predict(X[sel], beta)
    psi_real, hajek_real = dr_estimate(Y, H, Creal, Vreal, Treal, G_real, mu_rows,
                                       run_of, t_rows)
    print(f"early_exit real case: KM Hajek {hajek_real*100:.3f}%  DR {psi_real*100:.3f}%")

    payload = {"kind": "doubly_robust", "seed": SEED, "n_rep": N_REP,
               "features": names, "identity_check_abs_err": ident_err,
               "auc_by_step": auc_by_t, "coef_full_data": dict(zip(names, beta_full.tolist())),
               "simulation": results,
               "early_exit_real": {"km_hajek_pct": hajek_real * 100, "dr_pct": psi_real * 100}}
    (OUT / "dr_estimator.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"wrote {OUT / 'dr_estimator.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
