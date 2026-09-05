"""Regenerate every censoring result and figure cited in the paper.

    uv run python scripts/censoring/reproduce_all.py

Stages:
  1. build_summary       -- pull 5 pruned columns from the public dataset
                            (~0.6 MB of a 1.11 GB corpus) -> trajectory_summary.parquet
  2. audit_step_counts   -- re-fetch 20 full trajectories (seed 20260905) and
                            verify the step-count parser exactly
  3. audit_exit_status   -- exit-status / target / horizon association table
  4. analyze             -- analytic bias, IPCW Monte Carlo, model-level
                            ranking, horizon strata, stress test, Figure 1

Stage 1 and 2 need network access to Hugging Face; stages 3 and 4 are offline
once the summary parquet exists. No paid API and no model inference at any
stage. Pass --skip-fetch to rerun only the offline stages.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SUMMARY = REPO_ROOT / "results" / "censoring" / "trajectory_summary.parquet"

STAGES = [
    # primary corpus (SWE-agent)
    ("build_summary", "build_summary.py", True),
    ("audit_step_counts", "audit_step_counts.py", True),
    ("audit_exit_status", "audit_exit_status.py", False),
    ("analyze", "analyze.py", False),
    # secondary corpus (tau-bench)
    ("build_tau", "build_tau_summary.py", True),
    ("audit_tau_step_counts", "audit_tau_step_counts.py", False),
    ("analyze_tau", "analyze_tau.py", False),
    # cross-domain figure
    ("make_figures", "make_figures.py", False),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-fetch", action="store_true",
                    help="skip network stages; requires an existing summary parquet")
    ap.add_argument("--only", nargs="*", choices=[s[0] for s in STAGES])
    args = ap.parse_args()

    if args.skip_fetch and not SUMMARY.exists():
        print(f"ERROR: --skip-fetch needs {SUMMARY.relative_to(REPO_ROOT)}")
        return 2

    rc = 0
    for name, script, needs_net in STAGES:
        if args.only and name not in args.only:
            continue
        if args.skip_fetch and needs_net:
            print(f"[{name}] SKIPPED (--skip-fetch)")
            continue
        print(f"\n{'='*70}\n[{name}] running {script}\n{'='*70}", flush=True)
        t0 = time.time()
        r = subprocess.run([sys.executable, str(Path(__file__).parent / script)])
        print(f"[{name}] exit={r.returncode} in {time.time()-t0:.1f}s")
        if r.returncode != 0:
            print(f"[{name}] FAILED — stopping so no downstream result is built "
                  f"on an unvalidated stage.")
            return r.returncode
    print("\nAll stages complete. Results in results/censoring/, "
          "figure in tas_overleaf/figures/.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
