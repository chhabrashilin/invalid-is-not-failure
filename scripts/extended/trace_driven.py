"""Censoring driven by observed failure processes (extended paper).

Instead of a hypothetical constant hazard, we estimate step-wise hazards from
the invalidations actually recorded in public logs and apply them to every
model's outcome-horizon distribution:

  container   SWE-agent corpus, early_exit (container runtime errors)
  provider    frontier leaderboard, provider errors pooled over 39 submissions
  gemini-3-pro, qwen2.5-coder
              the provider-failure process one submission actually experienced

Hazards are Kaplan-Meier discrete hazards, pooled within step bands to avoid
noise. For each process and corpus we report the expected invalid fraction,
per-model policy biases, and expected pairwise reversals if every model were
exposed to that process.

    uv run python scripts/extended/trace_driven.py
"""

from __future__ import annotations

import csv
import json
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
from frontier_analysis import load as load_frontier, short  # noqa: E402

RES = REPO_ROOT / "results"
OUT = RES / "extended"
BANDS = [(1, 10), (11, 25), (26, 50), (51, 100), (101, 10**6)]
PROVIDER = ("APIError", "RetryError", "ServiceUnavailableError")


def band_hazard(H, E):
    """Band-pooled discrete hazard: events in band / run-steps at risk in band."""
    lam = []
    for lo, hi in BANDS:
        exposure = np.clip(np.minimum(H, hi) - lo + 1, 0, None).sum()
        ev = (E & (H >= lo) & (H <= hi)).sum()
        lam.append(ev / exposure if exposure else 0.0)
    return np.array(lam)


def survival_from_bands(lam, hmax):
    G = np.ones(hmax + 1)
    h = np.arange(1, hmax + 1)
    step_lam = np.zeros(hmax + 1)
    for (lo, hi), l in zip(BANDS, lam):
        step_lam[(np.arange(hmax + 1) >= lo) & (np.arange(hmax + 1) <= hi)] = l
    G[1:] = np.cumprod(1 - step_lam[1:])
    return G


def processes():
    t = pq.read_table(RES / "censoring" / "trajectory_summary.parquet")
    Hs = np.asarray(t.column("step_count")).astype(int)
    Es = np.asarray(t.column("exit_status")).astype(str) == "early_exit"
    sub, H, Y, cost, st, cls = load_frontier()
    Ef = cls == "censored"
    out = {"container (SWE-agent early_exit)": band_hazard(Hs, Es),
           "provider (frontier, pooled)": band_hazard(H, Ef)}
    for name in ("gemini-3-pro-high", "qwen2-5-coder-32b-instruct"):
        m = np.array([short(s) == name for s in sub])
        out[f"provider ({name} as observed)"] = band_hazard(H[m], Ef[m])
    return out


def corpora():
    sub, H, Y, cost, st, cls = load_frontier()
    k = cls == "outcome"
    rows = list(csv.DictReader(open(OUT / "multilingual_runs.csv", encoding="utf-8")))
    t = pq.read_table(RES / "censoring" / "tau_trajectory_summary.parquet")
    return {
        "frontier (Verified)": (H[k], Y[k], sub[k], 100),
        "frontier (Multilingual)": (np.array([int(float(r["api_calls"])) for r in rows]),
                                    np.array([r["resolved"] == "True" for r in rows], dtype=float),
                                    np.array([r["submission"] for r in rows]), 100),
        "tau-bench": (np.asarray(t.column("step_count")).astype(int),
                      (np.asarray(t.column("score")).astype(float) == 1).astype(float),
                      np.asarray(t.column("model_path")).astype(str), 100),
    }


def evaluate(G, H, Y, M, min_n):
    names = [m for m in sorted(set(M.tolist())) if (M == m).sum() >= min_n]
    per, p_true, p_cc, p_fail = [], [], [], []
    for m in names:
        h, y = H[M == m], Y[M == m]
        w = G[np.minimum(h, len(G) - 1)]
        pt, pc, pf = y.mean(), (y * w).sum() / w.sum(), (y * w).mean()
        p_true.append(pt), p_cc.append(pc), p_fail.append(pf)
        per.append({"m": float(1 - w.mean()), "bias_fail_pp": float((pf - pt) * 100),
                    "bias_cc_pp": float((pc - pt) * 100)})
    p_true, p_cc, p_fail = map(np.array, (p_true, p_cc, p_fail))

    def rev(obs):
        dt = np.sign(p_true[:, None] - p_true[None, :])
        do = np.sign(obs[:, None] - obs[None, :])
        return int(np.triu((dt != 0) & (do != 0) & (dt != do), 1).sum())
    n = len(names)
    return {"n_models": n, "pairs": n * (n - 1) // 2,
            "mean_invalid_pct": float(np.mean([p["m"] for p in per]) * 100),
            "reversals_fail": rev(p_fail), "reversals_cc": rev(p_cc),
            "max_abs_bias_fail_pp": float(max(abs(p["bias_fail_pp"]) for p in per)),
            "max_abs_bias_cc_pp": float(max(abs(p["bias_cc_pp"]) for p in per))}


def main() -> int:
    procs = processes()
    cors = corpora()
    hmax = max(int(c[0].max()) for c in cors.values()) + 1
    report = {"bands": BANDS, "hazards_pct": {k: (v * 100).tolist() for k, v in procs.items()},
              "results": {}}
    for pname, lam in procs.items():
        G = survival_from_bands(lam, hmax)
        print(f"\n== {pname}: band hazards (%) {np.round(lam * 100, 3).tolist()}")
        report["results"][pname] = {}
        for cname, (H, Y, M, mn) in cors.items():
            r = evaluate(G, H, Y, M, mn)
            report["results"][pname][cname] = r
            print(f"   {cname}: invalid {r['mean_invalid_pct']:.1f}%  reversals fail "
                  f"{r['reversals_fail']}/{r['pairs']}  cc {r['reversals_cc']}  "
                  f"max|bias| fail {r['max_abs_bias_fail_pp']:.2f} cc {r['max_abs_bias_cc_pp']:.2f}")
    (OUT / "trace_driven.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
