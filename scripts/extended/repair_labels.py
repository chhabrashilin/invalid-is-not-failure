"""Repair resolution labels for bash-only submissions whose
per_instance_details.json disagrees with their own metadata.yaml score.

For those submissions we read logs/<instance>/report.json from the public S3
bucket (the evaluation harness's verdict). A missing report means the public
artifact holds no verdict for that run; it is labelled "no_report" and treated
as unattributable, never as a failure.

    uv run python scripts/extended/repair_labels.py
"""

from __future__ import annotations

import csv
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from fetch_bash_only_exits import RAW, OUT, S3, get

TOL_PP = 0.25


def verdict(sub: str, inst: str):
    b = get(f"{S3}/bash-only/{sub}/logs/{inst}/report.json")
    if b is None:
        return None
    try:
        d = json.loads(b)
    except json.JSONDecodeError:
        m = re.search(rb'"resolved":\s*(true|false)', b)
        return None if m is None else m.group(1) == b"true"
    if inst in d and isinstance(d[inst], dict):  # swebench harness nests by id
        d = d[inst]
    return bool(d.get("resolved"))


def main() -> int:
    path = OUT / "bash_only_runs.csv"
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    subs = sorted({r["submission"] for r in rows})
    broken = []
    for s in subs:
        meta = yaml.safe_load(open(RAW / "verified" / s / "metadata.yaml", encoding="utf-8"))
        meta_score = float(meta["info"]["resolved"])
        rs = [r for r in rows if r["submission"] == s]
        pid_score = 100 * sum(r["resolved"] == "True" for r in rs) / len(rs)
        if abs(meta_score - pid_score) > TOL_PP:
            broken.append((s, meta_score, pid_score))
    report = {"tolerance_pp": TOL_PP, "repaired": []}
    for s, meta_score, pid_score in broken:
        rs = [r for r in rows if r["submission"] == s]
        with ThreadPoolExecutor(32) as ex:
            vs = list(ex.map(lambda r: verdict(s, r["instance_id"]), rs))
        for r, v in zip(rs, vs):
            r["label_source"] = "report.json"
            r["resolved"] = str(bool(v)) if v is not None else "False"
            r["no_report"] = str(v is None)
        n_rep = sum(v is not None for v in vs)
        n_res = sum(bool(v) for v in vs)
        info = {"submission": s, "metadata_score": meta_score,
                "per_instance_score": pid_score, "reports": n_rep,
                "resolved_in_reports": n_res,
                "rebuilt_score_over_500": 100 * n_res / len(rs)}
        report["repaired"].append(info)
        print(info)
    for r in rows:
        r.setdefault("label_source", "per_instance_details.json")
        r.setdefault("no_report", "False")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (OUT / "label_repair.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
