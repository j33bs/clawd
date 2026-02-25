# Runtime QUIESCE Mode

Use `OPENCLAW_QUIESCE=1` before audits or commits to prevent background writers from mutating protected state files.

Protected files:
- `workspace/state/tacti_cr/events.jsonl`
- `workspace/research/findings.json`
- `workspace/research/queue.json`
- `workspace/research/wander_log.md`

Usage (must be sourced in the current shell):
- `source workspace/scripts/quiesce_on.sh`
- `source workspace/scripts/quiesce_off.sh`

Required practice for audit/commit windows:
- Enable quiesce before evidence collection and commits.
- Disable quiesce after the protected window.

Policy router log clarification:
- `workspace/scripts/policy_router.py` default router telemetry is `itc/llm_router_events.jsonl` (separate log, not protected here).
- It can also write to `workspace/state/tacti_cr/events.jsonl` via TACTI fallback paths; that protected path is quiesce-guarded.

Status helper:
- `source workspace/scripts/quiesce_status.sh`
