# TeamChat

TeamChat runs a two-agent loop with shared local memory and append-only evidence:

- Planner agent: produces `plan` JSON and `work_orders` JSON.
- Coder agent: executes one work order, runs allowlisted commands, emits `patch_report` JSON.
- Planner review: returns `accept`, `revise`, or `request_input`.

## Storage layout

The session store is local and authoritative:

- `workspace/teamchat/sessions/<id>.jsonl`
- `workspace/teamchat/summaries/<id>.md`
- `workspace/teamchat/state/<id>.json`

Each tool call is logged as JSONL (`event=tool_call`) with command, allowlist decision, and exit code.

## Governance controls

Kill-switch and budgets are enforced per session:

- `--max-cycles`
- `--max-commands-per-cycle`
- `--max-consecutive-failures`

TeamChat is explicit opt-in only (CLI run). It does not alter default chat routing.

## Offline verification (default)

```bash
bash workspace/scripts/verify_team_chat.sh
```

This uses fake adapters and deterministic outputs. No network calls required.

## Live adapters

Enable real planner/coder adapters via `--live`:

```bash
python3 workspace/scripts/team_chat.py \
  --task "Implement small verified change" \
  --session-id teamchat_live_example \
  --max-cycles 3 \
  --max-commands-per-cycle 4 \
  --live
```

Live mode uses `PolicyRouter.execute_with_escalation` and logs selected provider/model decisions in `event.meta.route`.
Planner prompts include explicit `use chatgpt`, coder prompts include explicit `use codex`.
If auth is unavailable, the run fails closed with recorded route reasons.

## Command allowlist (live coder)

Allowed by default:

- `git status|diff|log`
- `python3 -m py_compile ...`
- `npm test`
- `bash workspace/scripts/verify_*.sh`

Add additional regex patterns only via explicit `--allow-cmd`.
