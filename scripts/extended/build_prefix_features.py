"""Per-step prefix records for the SWE-agent corpus (extended paper).

For each trajectory we keep one small record per agent decision step
(role == "ai"): the command category of the action and two flags on the
observation that follows it. A censored run at step t reveals exactly the
records of steps 1..t-1, so these are the features a deployed harness would
have when an infrastructure failure strikes.

Rows are emitted in the same shard order as build_summary.py, and the step
count of every row is checked against trajectory_summary.parquet.

    uv run python scripts/extended/build_prefix_features.py
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path

import fsspec
import numpy as np
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / "results" / "extended"
SUMMARY = REPO_ROOT / "results" / "censoring" / "trajectory_summary.parquet"
PARQUET_API = ("https://huggingface.co/api/datasets/nebius/"
               "SWE-agent-trajectories/parquet/default/train")

# command categories
OTHER, NAV, EDIT, CREATE, RUN, SUBMIT = range(6)
NAV_CMDS = {"open", "goto", "scroll_down", "scroll_up", "find_file", "search_dir",
            "search_file", "ls", "cat", "grep", "find", "head", "tail", "cd", "pwd"}
RUN_CMDS = {"python", "python3", "pytest", "bash", "sh", "make", "tox"}
BLOCK = re.compile(r"```[a-zA-Z]*\n(.*?)```", re.S)
ERR = re.compile(r"Traceback \(most recent call last\)|\bError\b|\bFAILED\b")
EDIT_FAIL = "Your proposed edit has introduced new syntax error"
# observation looks like passing tests / a successful script run
PASS = re.compile(r"\b\d+ passed\b|\bOK\b|\bpassed\b|[Ss]uccess(fully)?\b|All tests")
# action runs tests, or runs / creates a reproduction script
TEST_CMD = re.compile(r"pytest|unittest|tox\b|runtests|manage\.py test|\btest_\w*\.py")
REPRO_CMD = re.compile(r"reproduce|repro\b|reproduction")


def command_code(text: str) -> int:
    blocks = BLOCK.findall(text or "")
    if not blocks:
        return OTHER
    cmd = blocks[-1].strip().split()
    if not cmd:
        return OTHER
    head = cmd[0]
    if head == "edit":
        return EDIT
    if head == "create":
        return CREATE
    if head == "submit":
        return SUBMIT
    if head in RUN_CMDS:
        return RUN
    if head in NAV_CMDS:
        return NAV
    return OTHER


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    urls = json.load(urllib.request.urlopen(PARQUET_API))
    fs = fsspec.filesystem("http")
    codes, obs_err, edit_fail, lengths = [], [], [], []
    obs_pass, cmd_test, cmd_repro = [], [], []
    t0 = time.time()
    for si, url in enumerate(urls):
        for attempt in range(5):
            s_codes, s_err, s_fail, s_len = [], [], [], []
            s_pass, s_test, s_repro = [], [], []
            try:
                pf = pq.ParquetFile(fs.open(url))
                rg0 = pf.metadata.row_group(0)
                leafs = [rg0.column(i).path_in_schema for i in range(rg0.num_columns)]
                role_leaf = next(k for k in leafs if k.endswith(".role"))
                text_leaf = next(k for k in leafs if k.endswith(".text"))
                for rg in range(pf.metadata.num_row_groups):
                    tbl = pf.read_row_group(rg, columns=[role_leaf, text_leaf])
                    for traj in tbl.column(0).to_pylist():
                        n = 0
                        prev_ai = False
                        for m in traj:
                            role, text = m.get("role"), m.get("text") or ""
                            if role == "ai":
                                s_codes.append(command_code(text))
                                s_err.append(0)
                                s_fail.append(0)
                                s_pass.append(0)
                                blocks = BLOCK.findall(text)
                                cmd = blocks[-1] if blocks else ""
                                s_test.append(int(bool(TEST_CMD.search(cmd))))
                                s_repro.append(int(bool(REPRO_CMD.search(cmd))))
                                n += 1
                                prev_ai = True
                            elif role == "user" and prev_ai:
                                s_err[-1] = int(bool(ERR.search(text)))
                                s_fail[-1] = int(EDIT_FAIL in text)
                                s_pass[-1] = int(bool(PASS.search(text)))
                                prev_ai = False
                        s_len.append(n)
                break
            except Exception as exc:  # transient HTTP range errors
                print(f"  shard {si + 1} attempt {attempt + 1} failed: "
                      f"{type(exc).__name__}: {exc}", flush=True)
                if attempt == 4:
                    raise
                time.sleep(5 * (attempt + 1))
        codes += s_codes
        obs_err += s_err
        edit_fail += s_fail
        obs_pass += s_pass
        cmd_test += s_test
        cmd_repro += s_repro
        lengths += s_len
        print(f"shard {si + 1}/{len(urls)} rows={len(lengths)} "
              f"steps={len(codes)} {time.time() - t0:.0f}s", flush=True)

    lengths = np.asarray(lengths, dtype=np.int32)
    H = np.asarray(pq.read_table(SUMMARY).column("step_count")).astype(np.int32)
    assert len(H) == len(lengths), (len(H), len(lengths))
    mismatch = int((H != lengths).sum())
    print(f"step-count mismatches vs summary: {mismatch}")
    assert mismatch == 0
    np.savez_compressed(OUT / "swe_prefix_records.npz",
                        codes=np.asarray(codes, dtype=np.uint8),
                        obs_err=np.asarray(obs_err, dtype=np.uint8),
                        edit_fail=np.asarray(edit_fail, dtype=np.uint8),
                        obs_pass=np.asarray(obs_pass, dtype=np.uint8),
                        cmd_test=np.asarray(cmd_test, dtype=np.uint8),
                        cmd_repro=np.asarray(cmd_repro, dtype=np.uint8),
                        lengths=lengths)
    print(f"wrote {OUT / 'swe_prefix_records.npz'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
