# Phase 0 Runbook

Exact commands to reproduce the Phase 0 infrastructure validation from a clean
checkout. Phase 0 produces **no scientific result**: it validates machinery only.

---

## 0. Cost gate (read this first)

Before any paid model API is used, `docs/research_log.md` must contain a line:

```
PHASE_0_API_BUDGET_USD = <amount>
```

**As of this runbook that line does not exist, so paid API calls are forbidden.**
Phase 0 therefore runs with a deterministic mock LM
(`src/instrumentation/mock_lm.py`). Every mocked session records
`model_id = "mock:..."` so mocked runs can never be mistaken for real
trajectories during later analysis.

---

## 1. Prerequisites

| Requirement | Verify with | Notes |
|---|---|---|
| `uv` | `uv --version` | validated with 0.11.19 |
| Docker Desktop, Linux containers | `docker info` | daemon must be running |
| Disk | ~10 GB free | the SWE-bench instance image is ~4.2 GB |
| RAM | Docker VM ≥ 6 GB | validated with 7.58 GB |
| Network | — | pulls the image and reads the HF datasets-server |

Start Docker Desktop if the daemon is not reachable:

```powershell
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
# then poll until ready:
docker info --format "{{.ServerVersion}}"
```

---

## 2. Environment

```bash
uv python pin 3.12
uv sync --group dev
uv run python -c "import sys, pydantic, yaml, docker; print(sys.version)"
```

`pyproject.toml` + `uv.lock` are the reproducible dependency record. No
torch/CUDA is installed: there is no NVIDIA GPU on this machine and Stage 3
Plan B does not require one.

---

## 3. Select the benchmark instance

The selection rule is **pre-declared and success-blind**: the lexicographically
first `instance_id` in SWE-bench_Verified.

```bash
uv run python scripts/phase0/select_instance.py
# -> configs/phase0/selected_instance.json
```

Result: `astropy__astropy-12907`. The rule depends only on instance naming, not
on difficulty or any expectation of success, so it cannot be tuned to obtain a pass.

---

## 4. Pull the instance image

```bash
docker pull swebench/sweb.eval.x86_64.astropy_1776_astropy-12907:latest
```

(~4.16 GB. The `__` in the instance id becomes `_1776_` in the image name.)

---

## 5. Run the tests

```bash
uv run pytest
```

All tests must pass before the pipeline is run. The leakage tests in
`tests/test_oracle_leakage.py` are the ones that protect scientific validity —
if they fail, no measurement from this harness can be trusted.

---

## 6. Run the Phase 0 pipeline

```bash
uv run python scripts/phase0/run_phase0.py --config configs/phase0/smoke.yaml
```

This single command performs the whole smoke pipeline:

1. verifies the Docker daemon and image (P0.2)
2. starts the instance container (P0.3)
3. runs 3 instrumented prefix steps, logging the Stage 3 schema (P0.4)
4. `docker commit`s a checkpoint at the pre-declared step (P0.6)
5. runs the parent to termination
6. runs the **independent** evaluator on the instance's real `FAIL_TO_PASS`
   tests (P0.5)
7. restores three continuations from the checkpoint (P0.7, P0.8)
8. forks two same-seed replicates plus one different-seed replicate and measures
   divergence (P0.9)
9. hashes all raw artifacts and re-verifies the parent manifest after forking
   (P0.11)

Outputs:

```
data/raw/phase0-smoke-001/<session_id>/{session.json,steps.jsonl,outcome.json,evaluation.json,manifest.json}
artifacts/phase0/phase0-smoke-001/{phase0_report.json,snapshot.json,evaluator/}
```

Add `--keep-images` to retain the checkpoint image for inspection.

---

## 7. Verify raw-data integrity independently

```bash
uv run python -c "
import sys; sys.path.insert(0,'src')
from pathlib import Path
from trajectory.store import verify_manifest
for d in sorted(Path('data/raw/phase0-smoke-001').iterdir()):
    print(d.name, verify_manifest(d))
"
```

Raw artifacts are written once, hashed into `manifest.json`, then made
read-only. **Never edit a raw file.** If logging is wrong, fix the code and
re-run under a new `run_id`.

---

## 8. Clean up

```bash
docker ps -a --filter "ancestor=swebench/sweb.eval.x86_64.astropy_1776_astropy-12907:latest" -q | xargs -r docker rm -f
docker images "phase0/ckpt" -q | xargs -r docker rmi -f
# to reclaim ~4.2 GB:
# docker rmi swebench/sweb.eval.x86_64.astropy_1776_astropy-12907:latest
```

---

## 9. Known limitations of this runbook

- **The LM is mocked.** Provider nondeterminism — the dominant source of fork
  divergence reported by arXiv:2608.08239 (74–77% swap divergence vs 6–35% for
  same-model controls) — is *not* exercised here and remains unmeasured.
- **`docker commit` is the snapshot mechanism.** Stage 3 records faster
  alternatives (Shepherd arXiv:2605.10913, Crab arXiv:2604.28138) and a warning
  that container commits may be too slow at scale (arXiv:2510.05556). Phase 0
  only establishes that snapshot/restore is possible.
- **Token counts under the mock LM are estimated** at ~4 chars/token by
  `estimate_tokens`. Real provider usage figures must replace this in Phase 1.
- **One instance only.** Nothing here supports any claim about SWE-bench
  generally.
