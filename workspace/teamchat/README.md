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
- Optional witness logging (`OPENCLAW_TEAMCHAT_WITNESS=1`) writes hash-chain entries to `workspace/state_runtime/teamchat/witness_ledger.jsonl`.
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

## Team Chat Witness (tamper-evident provenance)

Team Chat Witness provides cryptographic provenance for agent turns. It is not a summary system and it does not write memory.

What it records per witnessed turn:

- `session_id`
- `turn`
- `agent`
- `route`
- `message_hash` and `message_hash_version`
- `ts`
- optional upstream context fields in route metadata (for example arousal/valence/proprioception when present)

Enable Team Chat + Witness:

```bash
OPENCLAW_TEAMCHAT=1 OPENCLAW_TEAMCHAT_WITNESS=1 python3 workspace/scripts/team_chat.py --agents planner,coder,critic --session teamchat_demo --max-turns 3
```

Verify witness provenance:

```bash
bash workspace/scripts/verify_teamchat_witness.sh --session teamchat_demo
```

Artifacts:

- Session logs: `workspace/state_runtime/teamchat/sessions/*.jsonl` (ignored)
- Witness ledger: `workspace/state_runtime/teamchat/witness_ledger.jsonl` (ignored)

Failure modes:

- `ledger_chain_invalid`: tampered entry or hash/sequence gap in witness ledger.
- `referenced_session_missing`: witness entry points to a session that does not exist.
- `session_message_missing`: witness turn does not map to an agent message in session JSONL.
- `message_hash_mismatch`: session message content/metadata differs from committed hash.
