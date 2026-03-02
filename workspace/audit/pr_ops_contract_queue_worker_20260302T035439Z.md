# ops(contract): policy thresholds + heavy queue/worker + backlog bias

## What Changed
- Added governed threshold policy file:
  - `workspace/governance/policy/contract_thresholds.json`
- Updated contract manager to load policy from:
  - `OPENCLAW_CONTRACT_POLICY_PATH` (if set), else default policy file path.
  - Emits `policy_source` and `queue_depth` in contract state.
- Added backlog-pressure mode bias guardrails:
  - Queue depth can bias SERVICE->CODE only when idle and EWMA is below low threshold.
  - Active manual SERVICE override remains authoritative.
- Extended heavy queue/worker lifecycle:
  - Queue schema supports `requires_gpu` + `tool_id`.
  - Worker invokes `ensure_coder_vllm_up.py` for GPU jobs before execution.
  - Writes ensure timing/results into run artifacts; fails cleanly when ensure fails.
- Added deterministic tests for policy loading, queue schema, worker ensure path, and queue-depth bias.

## Why
- Governance-first application of calibrated thresholds (policy file, not hardcoded runtime edits).
- LOAR alignment: regulated GPU lifecycle and controlled CODE windows.
- Safety and reversibility with evidence-gated operation.

## Evidence
- `workspace/audit/_evidence/contract_queue_calibrate_20260302T022709Z`
- `workspace/audit/_evidence/commit_calibrate_worker_20260302T025043Z`
- `workspace/audit/_evidence/next6_20260302T035439Z`

## Host Change Note
- `openclaw-heavy-worker.timer` is already installed/enabled (systemd user).

Rollback (host):
1. `systemctl --user disable --now openclaw-heavy-worker.timer`
2. `rm -f ~/.config/systemd/user/openclaw-heavy-worker.{service,timer}`
3. `systemctl --user daemon-reload`

## Risks + Mitigations
- Queue replay/drift risk:
  - Mitigation: queue depth excludes completed IDs using runs log; worker writes deterministic run records.
- Policy file safety:
  - Mitigation: constrained numeric key normalization and explicit `policy_source` telemetry.
- GPU startup flapping:
  - Mitigation: explicit ensure gate + policy classification (`POLICY` vs `FAULT`) and lock handling.

## Post-merge Checklist
1. Run `workspace/scripts/post_merge_verify_ops.sh`.
2. Confirm contract tick emits `mode/source/idle/ewma/queue_depth/policy_source`.
3. Confirm one queued no-op job drains and run artifacts/events are recorded.
