# Codex Efficiency Layer (CEL)

## Purpose
CEL adds a governed token-reduction operating layer to Codex session orchestration without changing routing contracts or security gates.

## Architecture Diagram (Text)

```text
User Intent
  -> CEL Prompt Discipline (tools/codex_prepare_prompt.py)
  -> CEL Spawn Wrapper (tools/codex_spawn_session.py)
  -> ACP/OpenClaw Harness (gateway /api/agents/spawn)
  -> Session Runtime
     -> Token Watchdog (tools/codex_token_watchdog.py)
     -> Finalize + Export (tools/codex_finalize_session.py)
     -> Optional Cache Hook Surface (workspace/runtime/codex_cache_hooks.py)
```

## Workflow Lifecycle
1. Prepare prompt artifact:
   - Validate required sections: `GOAL`, `INPUTS`, `OUTPUTS`, `CONSTRAINTS`, `SUCCESS_CRITERIA`.
   - Emit `workspace/runtime/codex_prepared_prompt.json` with token baseline metadata.
2. Spawn session through CEL wrapper:
   - Read prepared artifact.
   - Attach referenced file metadata/excerpts.
   - Spawn persistent session (`thread=true`, `mode=session`).
   - Apply model strategy defaults (draft lightweight; explicit escalation for full codex).
   - Append session log row to `workspace/runtime/codex_sessions.log`.
3. Observe token usage:
   - Poll session status.
   - Write metrics to `workspace/runtime/token_metrics.jsonl`.
   - Emit warning for spike deltas above threshold; no automatic kill.
4. Finalize session:
   - Pull session history/status.
   - Export artifacts to `workspace/runtime/codex_outputs/<session_id>/`.
   - Record token totals and termination outcome.

## Operator Commands

```bash
python tools/codex_prepare_prompt.py codex_prompt.md

python tools/codex_spawn_session.py \
  --prepared workspace/runtime/codex_prepared_prompt.json \
  --gateway-url http://127.0.0.1:18789

python tools/codex_token_watchdog.py \
  --session-id <session_id> \
  --gateway-url http://127.0.0.1:18789 \
  --iterations 10

python tools/codex_finalize_session.py \
  --session-id <session_id> \
  --gateway-url http://127.0.0.1:18789

bash tools/verify_codex_efficiency_layer.sh
```

## Rollback Procedure
1. Revert CEL files and integration commit:
   - Refresh upstream refs and restore tracked integration file from upstream:
   - `git fetch origin`
   - `git restore --source=origin/main -- workspace/scripts/message_handler.py`
   - Offline-safe fallback if `origin` is unavailable:
   - `BASE=$(git merge-base HEAD main 2>/dev/null || git merge-base HEAD origin/main)`
   - `git restore --source="$BASE" -- workspace/scripts/message_handler.py`
   - `tools/codex_prepare_prompt.py`
   - `tools/codex_spawn_session.py`
   - `tools/codex_token_watchdog.py`
   - `tools/codex_finalize_session.py`
   - `tools/verify_codex_efficiency_layer.sh`
   - `workspace/runtime/codex_cache_hooks.py`
   - `workspace/docs/codex_efficiency_layer.md`
2. Remove runtime artifacts if desired:
   - `workspace/runtime/codex_prepared_prompt.json`
   - `workspace/runtime/codex_sessions.log`
   - `workspace/runtime/token_metrics.jsonl`
   - `workspace/runtime/codex_outputs/`
3. Re-run existing gateway and policy verification scripts.
