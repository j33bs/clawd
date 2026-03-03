# XCI Store Hardening Verification (Gates 5/6/7 + retro_dark + HUMAN_OK)

- Timestamp (UTC): 2026-02-24T03:55:23Z
- Branch: `claude-code/governance-session-20260223`
- HEAD at start of audit: `2d46e63e6cb55ad1d8da689908ca23b8465746ed`

## Phase 0 - Environment checks

Commands and outcomes:

1. `pwd`
- PASS: `/Users/heathyeager/clawd`

2. `git status --short`
- PASS: working tree had tracked edits before verification (`workspace/governance/SOUL.md`, `workspace/store/api.py`, `workspace/store/gates.py`, `workspace/store/run_gates.py`).

3. `command -v python3`
- PASS: `/opt/homebrew/bin/python3`

4. `python3 -c "import sys; print(sys.executable)"`
- PASS: `/opt/homebrew/opt/python@3.14/bin/python3.14`

5. `python3 -c "import lancedb; print('lancedb ok')"`
- FAIL: `ModuleNotFoundError: No module named 'lancedb'`

Repo runtime used for verification (no dependency installs):
- `workspace/venv/bin/python` (confirmed: `lancedb ok`)

## Phase 1 - Compile + gates end-to-end

Commands and outcomes:

1. `workspace/venv/bin/python -m py_compile workspace/store/gates.py workspace/store/run_gates.py workspace/store/api.py`
- PASS

2. `HF_HUB_OFFLINE=1 workspace/venv/bin/python workspace/store/run_gates.py`
- PASS (offline model cache mode)

### Gate summary (1-7)

- Gate 1: PASS
- Gate 2: PASS
- Gate 3: PASS (`4.1s`, threshold `<60s`)
- Gate 4: PASS
- Gate 5: PASS
- Gate 6: PASS
- Gate 7: PASS
- Overall: `ALL GATES PASSED — store is LIVE`

Detailed observations:
- Gate 5 authority invariance: Path A and Path B both returned canonical ids `[67, 88]` (top ids), same size and order.
- Gate 6 flow invariance: `linear_tail(5)` ids `[88,89,90,91,92]` matched `linear_tail(40)[-5:]` exactly.
- Gate 7 rebuild invariance: filed→canonical and canonical→filed mappings identical across two rebuilds.

Blocked-by-data conditions:
- None during this run (Gate 5 had valid EXEC:GOV candidates).

## Phase 2 - API smoke

Attempted to start existing FastAPI app on `127.0.0.1:8000` and run required curls.

Result:
- NOT RUNNABLE in this sandbox runtime.
- Uvicorn startup reached app init, but bind failed:
  - `[Errno 1] error while attempting to bind on address ('127.0.0.1', 8000): [errno 1] operation not permitted`

Therefore required curls were not executable here:
- `curl -s "http://127.0.0.1:8000/status"`
- `curl -s "http://127.0.0.1:8000/tail?n=50"`
- `curl -s "http://127.0.0.1:8000/tail?n=200&retro_dark=true"`
- `curl -s "http://127.0.0.1:8000/tail?n=200&retro_dark=false"`

## Notes on fixes applied during verification

- Gate 4 was kept metadata-only and non-mutating (no `table.update()` dependency).
- Gate 5 now prints explicit blocked-deployment notice when candidate pool is insufficient.
- Gate 6 row-equality check normalizes ndarray/list payloads before equality comparison.

## Final status

- Verification complete for gate path (1-7): PASS.
- API smoke blocked by local bind permissions in this execution sandbox.
