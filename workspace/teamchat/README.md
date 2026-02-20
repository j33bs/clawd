# Team Chat

Team Chat provides a governed multi-agent conversation workspace.

## Modes

- `Legacy planner/coder`: existing workflow used by `workspace/scripts/verify_team_chat.sh`.
- `Multi-agent Team Chat`: enabled with `--agents` and routed through `policy_router`.

## Multi-agent usage

```bash
OPENCLAW_TEAMCHAT=1 python3 workspace/scripts/team_chat.py \
  --agents planner,coder,critic \
  --session teamchat_demo \
  --max-turns 3
```

Optional one-shot mode:

```bash
OPENCLAW_TEAMCHAT=1 python3 workspace/scripts/team_chat.py \
  --agents planner,coder,critic \
  --session teamchat_demo \
  --max-turns 3 \
  --once \
  --message "Plan a safe patch sequence"
```

## Governance guarantees

- Default OFF: `OPENCLAW_TEAMCHAT` must be set to `1` for multi-agent mode.
- Append-only session logs: `workspace/state_runtime/teamchat/sessions/<session_id>.jsonl`.
- Optional witness logging (`OPENCLAW_TEAMCHAT_WITNESS=1`) writes hash-chain entries to `workspace/audit/witness_ledger.jsonl`.
- Auto-commit requires dual opt-in:
  - `TEAMCHAT_USER_DIRECTED_TEAMCHAT=1`
  - `TEAMCHAT_ALLOW_AUTOCOMMIT=1`
- Without dual opt-in, Team Chat does not commit changes.

## Message schema (JSONL)

Each line is deterministic JSON with:

- `ts`
- `role` (`user` or `agent:<name>`)
- `content`
- optional `route`
- optional `meta`
