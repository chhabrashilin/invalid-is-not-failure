"""Build the frontier-leaderboard corpus from the SWE-bench Verified bash-only
submissions (mini-SWE-agent scaffold, 500 tasks each).

Per run we record the horizon (api_calls), cost, and resolution from the
submission's per_instance_details.json, and the harness exit status read from
the public trajectory file on S3. Trajectories are large, so we read only the
bytes that hold "exit_status": the file head first (mini-SWE-agent v1 puts info
first), then growing suffix ranges (v2 and SWE-agent formats put it last).

    uv run python scripts/extended/fetch_bash_only_exits.py
"""

from __future__ import annotations

import csv
import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW = REPO_ROOT / "data" / "raw" / "swebench_experiments"
OUT = REPO_ROOT / "results" / "extended"
S3 = "https://swe-bench-submissions.s3.amazonaws.com"
EXIT_RE = re.compile(rb'"exit_status":\s*"((?:[^"\\]|\\.)*)"')
WORKERS = 32


def get(url: str, rng: str | None = None) -> bytes | None:
    req = urllib.request.Request(url, headers={"Range": f"bytes={rng}"} if rng else {})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (404, 403, 416):
                return None
            time.sleep(1 + attempt)
        except Exception:
            time.sleep(1 + attempt)
    return None


def list_keys(prefix: str) -> list[str]:
    keys, token = [], None
    while True:
        url = f"{S3}/?list-type=2&prefix={prefix}&max-keys=1000"
        if token:
            url += "&continuation-token=" + urllib.parse.quote(token)
        body = get(url) or b""
        keys += [k.decode() for k in re.findall(rb"<Key>([^<]*)</Key>", body)]
        m = re.search(rb"<NextContinuationToken>([^<]*)</NextContinuationToken>", body)
        if not m:
            return keys
        token = m.group(1).decode()


def exit_status(key: str) -> tuple[str | None, int]:
    url = f"{S3}/{key}"
    fetched = 0
    for rng in ("0-4095", "-8192", "-131072", "-1048576"):
        b = get(url, rng)
        if b is None:
            continue
        fetched += len(b)
        m = EXIT_RE.search(b) if rng.startswith("0") else None
        if not rng.startswith("0"):
            hits = EXIT_RE.findall(b)
            m = hits[-1] if hits else None
            if m:
                return m.decode(), fetched
        elif m:
            return m.group(1).decode(), fetched
    return None, fetched


def main() -> int:
    import urllib.parse  # noqa: F401  (used in list_keys)
    OUT.mkdir(parents=True, exist_ok=True)
    subs = sorted(p.name for p in (RAW / "verified").iterdir()
                  if p.is_dir() and not (p / "results.json").exists())
    sha = json.loads((RAW / "manifest.json").read_text())["commit"]
    rows, total_bytes = [], 0
    for sub in subs:
        d = RAW / "verified" / sub
        base = f"https://raw.githubusercontent.com/swe-bench/experiments/{sha}/evaluation/verified/{sub}"
        for fn in ("per_instance_details.json", "metadata.yaml"):
            if not (d / fn).exists():
                b = get(f"{base}/{fn}")
                if b:
                    (d / fn).write_bytes(b)
        pid_path = d / "per_instance_details.json"
        if not pid_path.exists():
            print(f"skip {sub}: no per_instance_details.json")
            continue
        pid = json.loads(pid_path.read_text(encoding="utf-8"))
        keys = [k for k in list_keys(f"bash-only/{sub}/trajs/")
                if k.endswith(".traj.json") or k.endswith(".traj")]
        by_inst = {k.split("/")[-2]: k for k in keys}
        cache = d / "exit_status.json"
        done = json.loads(cache.read_text()) if cache.exists() else {}
        todo = [i for i in pid if i not in done and i in by_inst]
        with ThreadPoolExecutor(WORKERS) as ex:
            futs = {ex.submit(exit_status, by_inst[i]): i for i in todo}
            for f in as_completed(futs):
                st, nb = f.result()
                done[futs[f]] = st
                total_bytes += nb
        cache.write_text(json.dumps(done, indent=0), encoding="utf-8")
        for inst, v in pid.items():
            rows.append({"submission": sub, "instance_id": inst,
                         "api_calls": v.get("api_calls"), "cost": v.get("cost"),
                         "resolved": bool(v.get("resolved")),
                         "exit_status": done.get(inst),
                         "has_traj": inst in by_inst})
        n_missing = sum(done.get(i) is None for i in pid)
        print(f"{sub}: {len(pid)} runs, {len(keys)} trajs, exit_status missing {n_missing}",
              flush=True)
    with open(OUT / "bash_only_runs.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} runs; fetched {total_bytes / 1e6:.1f} MB of trajectory bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
