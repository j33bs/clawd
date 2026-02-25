# Runtime QUIESCE Mode

Use `OPENCLAW_QUIESCE=1` before audits or commits to prevent background writers from mutating protected state files.

Protected files:
- `workspace/state/tacti_cr/events.jsonl`
- `workspace/research/findings.json`
- `workspace/research/queue.json`
- `workspace/research/wander_log.md`

Required practice for audit/commit windows:
- Enable quiesce before evidence collection and commits.
- Disable quiesce after the protected window.

Helper scripts:
- `source workspace/scripts/quiesce_on.sh`
- `source workspace/scripts/quiesce_off.sh`
