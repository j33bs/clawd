# Peer Exchange Protocol (Tailscale) Evidence (20260223T005754Z)

## Commands
- python3 workspace/scripts/exchange_envelope.py --create ...
- python3 workspace/scripts/exchange_envelope.py --validate --path <envelope>
- python3 workspace/scripts/exchange_envelope.py --send --path <envelope> --to-node Dali

## Output
```text
{"path": "workspace/exchanges/envelopes/20260223T005617Z_C_Lawd_to_Dali.json", "status": "created"}
{"path": "workspace/exchanges/envelopes/20260223T005618Z_Dali_to_C_Lawd.json", "status": "created"}
--- validate ---
{"message": "ok", "status": "ok"}
{"message": "ok", "status": "ok"}
--- send hint ---
{"recommended_command": "tailscale file cp workspace/exchanges/envelopes/20260223T005617Z_C_Lawd_to_Dali.json Dali:", "status": "tailscale_not_found"}
```

## Scope Hygiene Note (2026-02-23T01:04:35Z)
- During verification runs, `workspace/state/tacti_cr/events.jsonl` was mutated incidentally.
- It was restored with `git restore --worktree --staged workspace/state/tacti_cr/events.jsonl` to keep this 10-item plan scope clean.
- Recommendation: exclude/ignore this mutable state path in verification workflows to reduce incidental drift.
