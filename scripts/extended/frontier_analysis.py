"""Frontier-leaderboard analysis (extended paper).

Corpus: SWE-bench Verified bash-only submissions (mini-SWE-agent, 500 tasks
per model), built by fetch_bash_only_exits.py. Horizon H = api_calls.

  1. Definition 1 applied to the harness exit statuses
  2. real invalidity per submission: leaderboard score (invalid-as-failure),
     assumption-free bounds, complete case, and Kaplan-Meier weighting with the
     observed failure step
  3. survival ratios and hypothetical-hazard ranking fragility for the frontier
  4. an unbounded metric: cost per task under each policy

    uv run python scripts/extended/frontier_analysis.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "censoring"))
from revision_analysis import km_censoring_survival  # noqa: E402

OUT = REPO_ROOT / "results" / "extended"
FINE_Q = np.round(np.arange(0.0001, 0.05 + 1e-12, 0.0001), 6)

CLASS = {
    # valid outcomes: the agent submitted, or exhausted a declared budget, or
    # produced malformed output / exited itself
    "Submitted": "outcome", "submitted": "outcome",
    "LimitsExceeded": "outcome", "submitted (exit_cost)": "outcome",
    "submitted (exit_format)": "outcome", "exit_format": "outcome",
    "exit_command": "outcome",
    # provider failures after the harness's own retries
    "APIError": "censored", "RetryError": "censored",
    "ServiceUnavailableError": "censored",
    # cannot be attributed from the status alone
    "Timeout": "unattributable", "submitted (exit_error)": "unattributable",
    "": "unattributable",
}


def excluded_submissions() -> dict:
    """Submissions whose labels cannot be recovered: per-instance file
    disagrees with metadata and fewer than 90% of evaluation reports exist."""
    rep = json.loads((OUT / "label_repair.json").read_text(encoding="utf-8"))
    return {r["submission"]: (f"per-instance labels disagree with metadata "
                              f"({r['per_instance_score']:.1f} vs {r['metadata_score']:.1f}%) "
                              f"and only {r['reports']}/500 evaluation reports are public")
            for r in rep["repaired"] if r["reports"] < 450}


def load():
    rows = list(csv.DictReader(open(OUT / "bash_only_runs.csv", encoding="utf-8")))
    excl = excluded_submissions()
    rows = [r for r in rows if r["submission"] not in excl]
    sub = np.array([r["submission"] for r in rows])
    H = np.array([int(float(r["api_calls"])) for r in rows])
    Y = np.array([r["resolved"] == "True" for r in rows], dtype=float)
    cost = np.array([float(r["cost"]) for r in rows])
    st = np.array([r["exit_status"] or "" for r in rows])
    cls = np.array([CLASS[s] for s in st])
    return sub, H, Y, cost, st, cls


def short(name: str) -> str:
    return name.split("_", 2)[-1]


def km_hajek(H, Y, event, valid):
    G = km_censoring_survival(H, event, int(H.max()) + 1)
    with np.errstate(divide="ignore"):
        w = np.where(valid, 1.0 / G[H], 0.0)
    return float((w * Y).sum() / w.sum())


def main() -> int:
    sub, H, Y, cost, st, cls = load()
    N_all = len(Y)
    out = {"n_runs": int(N_all), "n_submissions": int(len(set(sub))),
           "excluded": excluded_submissions(),
           "label_repair": json.loads((OUT / "label_repair.json").read_text())}
    print("excluded:", out["excluded"])

    # 1. exit-status classification
    table = []
    for s in sorted(set(st.tolist()), key=lambda x: -(st == x).sum()):
        m = st == s
        table.append({"exit_status": s or "(missing)", "n": int(m.sum()),
                      "n_submissions": int(len(set(sub[m]))),
                      "resolve_rate": float(Y[m].mean()),
                      "mean_H": float(H[m].mean()), "class": CLASS[s]})
    out["exit_table"] = table
    for r in table:
        print(f"{r['exit_status']:26} n={r['n']:6d} subs={r['n_submissions']:2d} "
              f"res={r['resolve_rate']:.3f} H={r['mean_H']:6.1f} {r['class']}")

    # 2. real invalidity per submission
    per = []
    for s in sorted(set(sub.tolist())):
        m = sub == s
        h, y, c = H[m], Y[m], cls[m]
        N = int(m.sum())
        cen, una = c == "censored", c == "unattributable"
        valid_strict, valid_broad = ~cen, ~(cen | una)
        S_strict = y[valid_strict].sum()
        S_broad = y[valid_broad].sum()
        row = {"submission": s, "model": short(s), "N": N,
               "score": float(y.mean()), "M_censored": int(cen.sum()),
               "M_unattrib": int(una.sum()),
               "bounds_strict": [float(S_strict / N), float((S_strict + cen.sum()) / N)],
               "bounds_broad": [float(S_broad / N),
                                float((S_broad + cen.sum() + una.sum()) / N)],
               "cc_strict": float(y[valid_strict].mean()),
               "km_strict": km_hajek(h, y, cen, valid_strict) if cen.any()
               else float(y.mean())}
        per.append(row)
    per.sort(key=lambda r: -r["score"])
    for i, r in enumerate(per):
        r["rank_leaderboard"] = i + 1
    for i, r in enumerate(sorted(per, key=lambda r: -r["km_strict"])):
        r["rank_km"] = i + 1
    affected = [r for r in per if r["M_censored"] + r["M_unattrib"] > 0]
    out["per_submission"] = per
    print("\nsubmissions with invalid runs:")
    for r in affected:
        print(f"  {r['model'][:38]:38} score={r['score']*100:5.1f} cens={r['M_censored']:3d} "
              f"unatt={r['M_unattrib']:2d} bounds={[round(x*100,1) for x in r['bounds_strict']]} "
              f"cc={r['cc_strict']*100:5.1f} km={r['km_strict']*100:5.1f} "
              f"rank {r['rank_leaderboard']}->{r['rank_km']}")

    # pairwise identification on the frontier leaderboard
    def ident(key):
        tot = ok = 0
        for i in range(len(per)):
            for j in range(i + 1, len(per)):
                a, b = per[i], per[j]
                if a["score"] == b["score"]:
                    continue
                tot += 1
                ok += a[key][0] > b[key][1]
        return tot, ok
    out["pairs_strict"] = ident("bounds_strict")
    out["pairs_broad"] = ident("bounds_broad")
    adj = [(a, b) for a, b in zip(per, per[1:]) if a["score"] > b["score"]]
    out["adjacent_strict"] = [len(adj), int(sum(a["bounds_strict"][0] > b["bounds_strict"][1]
                                                for a, b in adj))]
    print("pairs identified strict", out["pairs_strict"], "broad", out["pairs_broad"],
          "adjacent strict", out["adjacent_strict"])
    gaps = np.diff(sorted(r["score"] for r in per))
    out["median_adjacent_gap_pp"] = float(np.median(gaps) * 100)

    # 3. survival ratios on valid-outcome runs, hypothetical hazards
    keep = cls == "outcome"
    models = sorted(set(sub.tolist()))
    surv = []
    for s in models:
        m = keep & (sub == s)
        h, y = H[m], Y[m]
        r = {"model": short(s), "n": int(m.sum()), "p": float(y.mean()),
             "H1": float(h[y == 1].mean()), "H0": float(h[y == 0].mean())}
        for q in (0.01, 0.02):
            w = (1 - q) ** h
            pb1, pb0 = w[y == 1].mean(), w[y == 0].mean()
            r[f"rho_{q}"] = float(pb1 / pb0)
            r[f"cc_bias_{q}"] = float(((y * w).sum() / w.sum() - y.mean()) * 100)
            r[f"fail_bias_{q}"] = float(((y * w).mean() - y.mean()) * 100)
            r[f"m_{q}"] = float(1 - w.mean())
            # unbounded metric: mean cost per task, complete case vs truth
            cst = cost[m]
            r[f"cost_cc_rel_{q}"] = float((cst * w).sum() / w.sum() / cst.mean() - 1)
        surv.append(r)
    out["survival"] = surv
    rho1 = np.array([r["rho_0.01"] for r in surv])
    print(f"\nfrontier rho at q=1%: min {rho1.min():.3f} median {np.median(rho1):.3f} "
          f"max {rho1.max():.3f}; rho<1 for {(rho1 < 1).sum()}/{len(rho1)}")
    print("cc bias range", min(r["cc_bias_0.01"] for r in surv), max(r["cc_bias_0.01"] for r in surv))
    print("fail bias range", min(r["fail_bias_0.01"] for r in surv), max(r["fail_bias_0.01"] for r in surv))
    print("cost cc rel range", min(r["cost_cc_rel_0.01"] for r in surv),
          max(r["cost_cc_rel_0.01"] for r in surv))

    # first reversal among frontier models on a fine grid
    Hs = [H[keep & (sub == s)] for s in models]
    Ys = [Y[keep & (sub == s)] for s in models]
    p_true = np.array([y.mean() for y in Ys])
    first = {}
    for pol in ("cc", "fail"):
        first[pol] = None
        for q in FINE_Q:
            ws = [(1 - q) ** h for h in Hs]
            if pol == "cc":
                obs = np.array([(y * w).sum() / w.sum() for y, w in zip(Ys, ws)])
            else:
                obs = np.array([(y * w).mean() for y, w in zip(Ys, ws)])
            dt = np.sign(p_true[:, None] - p_true[None, :])
            do = np.sign(obs[:, None] - obs[None, :])
            rev = int(np.triu((dt != 0) & (do != 0) & (dt != do), 1).sum())
            if rev:
                first[pol] = {"q": float(q), "reversals": rev}
                break
    rev_at = {}
    for q in (0.005, 0.01, 0.02):
        ws = [(1 - q) ** h for h in Hs]
        for pol in ("cc", "fail"):
            obs = np.array([((y * w).sum() / w.sum()) if pol == "cc" else (y * w).mean()
                            for y, w in zip(Ys, ws)])
            dt = np.sign(p_true[:, None] - p_true[None, :])
            do = np.sign(obs[:, None] - obs[None, :])
            rev_at[f"{pol}_{q}"] = int(np.triu((dt != 0) & (do != 0) & (dt != do), 1).sum())
    out["first_reversal"] = first
    out["reversals_at"] = rev_at
    out["n_model_pairs"] = len(models) * (len(models) - 1) // 2
    print("first reversal", first, "reversals", rev_at, "of", out["n_model_pairs"])

    (OUT / "frontier_analysis.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {OUT / 'frontier_analysis.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
