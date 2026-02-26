# Run Harness + Adapter Parity + vLLM Gate (2026-02-26)

- branch: codex/feat/run-harness-adapter-parity-vllm-gate-20260226
- base_sha: 9a452c4
- generated_at_utc: 2026-02-26T11:47:30Z

## What Was Added

1. Run harness (`workspace/scripts/run_harness.py`)
- Resumable checkpoint runs with run-scoped state under `workspace/state_runtime/runs/<run_id>/`.
- Bounded artifact enforcement (`OPENCLAW_RUN_MAX_FILES`, `OPENCLAW_RUN_MAX_BYTES`) with kill switch.
- Checkpoint steps: memory maintenance (sandboxed), heartbeat consolidation, bounded orchestration outcomes.
- Final summary JSON + audit/env notes for each run.

2. Adapter outbound sanitizer parity
- Extended outbound channel sanitization coverage to gateway adapter sends via `/api/tool/message` in runtime overlay.
- Added teamchat channel support in `outbound_sanitize` (`message`/`text` fields + limits).
- Existing Telegram reply-mode hardening remains unchanged.

3. vLLM health gate (`workspace/scripts/vllm_health_gate.sh`)
- Adds preflight/nightly vLLM checks: canonical port ownership + `/health` check.
- Integrates with `scripts/ensure_port_free.sh --probe-only` (no kill in gate path).
- Wired into nightly health checks (`nightly_build.sh --nightly`) and optional runtime rebuild preflight (`OPENCLAW_VLLM_PREFLIGHT=1`).

## Default Behavior / Toggles

- `run_harness.py`
  - `--checkpoints` default `6`
  - `--checkpoint-interval-seconds` default `3600`
  - `--accelerated` uses `OPENCLAW_RUN_ACCELERATED_INTERVAL_SECONDS` (default `5`)
  - `--dry-run` skips external-dependent execution and timing sleeps
  - caps:
    - `OPENCLAW_RUN_MAX_FILES` default `10000`
    - `OPENCLAW_RUN_MAX_BYTES` default `209715200`
- `vllm_health_gate.sh`
  - `--preflight`: exits `42` when owner is unknown or health is down
  - `--nightly`: always exits `0`, emits warnings when unhealthy
- `rebuild_runtime_openclaw.sh`
  - `OPENCLAW_VLLM_PREFLIGHT=1` enables gate before rebuild
  - default `0` (non-blocking for existing rebuild flows)

## Verification Commands

```bash
python3 -m unittest -q \
  tests_unittest.test_memory_maintenance \
  tests_unittest.test_agent_orchestration \
  tests_unittest.test_run_harness \
  tests_unittest.test_vllm_health_gate

npm run typecheck:hardening
npm run test:hardening
npm run runtime:rebuild

python3 workspace/scripts/run_harness.py --checkpoints 2 --checkpoint-interval-seconds 2 --accelerated --dry-run
bash workspace/scripts/vllm_health_gate.sh --nightly || true
```

## Verification Output Summary

```text
python unittest suite: PASS (Ran 21 tests)
typecheck:hardening: PASS
test:hardening: PASS (11/11)
runtime:rebuild: PASS
run_harness dry-run: PASS (2/2 checkpoints, no kill switches)
vllm_health_gate --nightly: PASS (exit 0, warnings emitted when unhealthy)
```

## Notes

- Existing untracked runtime evidence directories were left untouched:
  - `workspace/state_runtime/**`
  - `workspace/audit/6h_run_*.md`
- Adapter parity was implemented at the runtime overlay outbound boundary for gateway channel sends and existing provider API sends.

## Rollback

Revert these commits in reverse order after merge:
- `fa8bd40` docs(audit): capture harness adapter parity and vllm gate evidence
- `6dae915` feat(vllm): add vllm health gate + probe-only wiring
- `4a29520` feat(outbound): extend outbound sanitizer parity + tests
- `1f6cd4b` feat(harness): add resumable run harness + tests
