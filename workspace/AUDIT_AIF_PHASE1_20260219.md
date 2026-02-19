# AIF Phase 1 Audit (2026-02-19)

## 1) Summary (2h timebox)
- Shipped P1: append-only external memory event store (JSONL backend) at `workspace/tacti_cr/external_memory.py`.
- Shipped P1: integration test with red->green evidence at `tests_unittest/test_tacti_cr_external_memory_integration.py`.
- Shipped P1: runnable demo writer at `workspace/scripts/external_memory_demo.py`.
- Shipped P2 (minimal interfaces):
  - `workspace/tacti_cr/efe_calculator.py`
  - `workspace/tacti_cr/curiosity.py`
  - `workspace/tacti_cr/active_inference_agent.py`
- Dominant test runner selected: `npm test` (meaningful suite exists and runs Node + Python unittest).

## 2) Commands Run + Outcomes
- Discovery (read-only):
  - `git status --porcelain -uall` (dirty baseline existed before this work)
  - `git rev-parse --short HEAD` -> `688d5cb`
  - `ls -la workspace`, `ls -la workspace/scripts`, `ls -la core` (success)
  - `rg -n "MEMORY|memory|jsonl|sqlite|event_log|artifact" -S .` (success)
  - `rg -n "integration|Integration Tests|CODEX_TASK_LIST" -S .` (success)
  - `cat workspace/CODEX_TASK_LIST.md` (success)
  - `npm test` -> failed (known unrelated blocker; see section 5)
  - `python3 -m pytest -q` -> failed (`No module named pytest`)
- Red->Green test evidence:
  - RED: `python3 -m unittest tests_unittest/test_tacti_cr_external_memory_integration.py`
    - `ModuleNotFoundError: No module named 'tacti_cr.external_memory'`
  - GREEN: `python3 -m unittest tests_unittest/test_tacti_cr_external_memory_integration.py`
    - `Ran 1 test ... OK`
- Additional validation:
  - `python3 -m py_compile workspace/tacti_cr/external_memory.py workspace/tacti_cr/efe_calculator.py workspace/tacti_cr/curiosity.py workspace/tacti_cr/active_inference_agent.py workspace/scripts/external_memory_demo.py` (pass)
  - `python3 -m unittest tests_unittest/test_tacti_cr_external_memory_integration.py tests_unittest/test_tacti_cr_integration.py` (pass)
  - `python3 workspace/scripts/external_memory_demo.py --n 3 --event-type smoke --payload '{"x":1}'` (pass, wrote artifacts)
  - `npm test` rerun -> still same unrelated blocker (section 5)

## 3) Artifacts Produced
- `workspace/artifacts/external_memory/events.jsonl`
- Demo output includes backend/path/last event timestamp for that store.

## 4) Tests (Current)
- Added: `tests_unittest/test_tacti_cr_external_memory_integration.py`
  - Verifies append/read order, required fields, and persisted storage non-empty.
- Existing targeted regression check:
  - `tests_unittest/test_tacti_cr_integration.py` still passes.
- Dominant suite status:
  - `npm test` currently fails on pre-existing governance invariant check unrelated to this feature.

## 5) Known Issues / Blockers (Move-On Protocol)
### Blocker A: Dominant suite already red in baseline
- Repro:
  - `npm test`
- Error:
  - `FAIL: repo-root governance file diverges from canonical: HEARTBEAT.md`
  - From: `tests_unittest/test_goal_identity_invariants.py`
- Suspected cause:
  - Existing repo-level governance drift/uncommitted baseline, not external-memory changes.
- Minimal-diff suggestion:
  - Restore/align canonical `HEARTBEAT.md` before requiring full-suite green for unrelated PRs.

### Blocker B: Pytest unavailable locally
- Repro:
  - `python3 -m pytest -q`
- Error:
  - `No module named pytest`
- Minimal-diff suggestion:
  - Add dev dependency bootstrap (`pip install -r requirements-dev.txt` or equivalent) and/or keep `unittest` as canonical local fallback.

## 6) Hardening Backlog (Prioritized)
### P0 (correctness / data-loss risk)
- Add fsync/atomic append strategy and optional file lock for concurrent writers to `events.jsonl`.
- Add JSONL corruption detection artifact (`workspace/artifacts/external_memory/health.json`) with bad-line counts.

### P1 (test / CI reliability)
- Make `npm test` governance invariant robust to known local drift modes or gate it behind a preflight canonical sync check.
- Add CI job for `tests_unittest/test_tacti_cr_external_memory_integration.py` and demo smoke command.

### P2 (ergonomics / cleanup)
- Add CLI subcommand wrapper (`workspace/scripts/external_memory_cli.py`) for append/read/health operations.
- Add retention/rotation policy for `events.jsonl` and companion index.

## 7) Next Recommended Branch / PR Plan
1. `task/aif-phase1-external-memory-hardening`
   - locking, atomic append, corruption counters, health artifact.
2. `task/aif-phase1-governance-test-stability`
   - isolate invariant failure modes and stabilize `npm test` baseline.
3. `task/aif-phase1-agent-composition`
   - wire `ActiveInferenceAgent` + `efe.evaluate` + `curiosity.epistemic_value` with dedicated integration tests.
