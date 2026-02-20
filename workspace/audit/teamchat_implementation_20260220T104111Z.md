# Team Chat Implementation Audit

- UTC: 20260220T104111Z
- Branch: codex/feature/team-chat-20260220

## Design Summary

Implemented a first-class Team Chat surface as a flag-gated multi-agent mode in `workspace/scripts/team_chat.py` with append-only session logs under ignored runtime state.

- Existing planner/coder TeamChat flow remains default and unchanged unless `--agents` is provided.
- New multi-agent mode is enabled only when `OPENCLAW_TEAMCHAT=1`.
- Agent turns are deterministic round-robin (user -> first agent -> next agent).
- Routing uses `PolicyRouter.execute_with_escalation` with intent family `teamchat:<agent>`.
- Witness entries are emitted per agent turn only when `OPENCLAW_TEAMCHAT_WITNESS=1`.
- Auto-commit remains governed by dual opt-in (`TEAMCHAT_USER_DIRECTED_TEAMCHAT=1` and `TEAMCHAT_ALLOW_AUTOCOMMIT=1`) using existing self-audit contract.

## Flags

- `OPENCLAW_TEAMCHAT` (default `0`): enables multi-agent Team Chat mode.
- `OPENCLAW_TEAMCHAT_WITNESS` (default `0`): emits witness ledger entries for Team Chat turns.
- `TEAMCHAT_USER_DIRECTED_TEAMCHAT` + `TEAMCHAT_ALLOW_AUTOCOMMIT` (default `0`): dual opt-in required before any auto-commit path can run.

## Files Added

- `workspace/teamchat/__init__.py`
- `workspace/teamchat/message.py`
- `workspace/teamchat/store.py`
- `workspace/teamchat/session.py`
- `workspace/teamchat/orchestrator.py`
- `tests_unittest/test_team_chat_basic.py`
- `tests_unittest/test_team_chat_witness.py`
- `tests_unittest/test_team_chat_no_side_effects.py`
- `tests_unittest/test_policy_router_teamchat_intent.py`

## Files Changed

- `workspace/scripts/team_chat.py`
  - Added multi-agent mode (`--agents`, `--session`, `--max-turns`, `--message`, `--once`, `--context-window`)
  - Added `OPENCLAW_TEAMCHAT` hard gate
  - Reused existing dual-opt-in autocommit enforcement in cycle end
- `workspace/scripts/policy_router.py`
  - Added intent aliasing for `teamchat:<agent>` to support per-agent routing config and safe fallback
  - Added budget key fallback so `teamchat:*` uses existing budget intent (e.g. `coding`) when configured
- `workspace/teamchat/README.md`
  - Documented Team Chat multi-agent mode, flags, governance guarantees, and schema
- `README.md`
  - Added Team Chat feature notes and flags under feature flags section

## Tests Added

- `tests_unittest/test_team_chat_basic.py`
  - Verifies append-only JSONL ordering and round-robin speaker order
  - Verifies writes are confined to `workspace/state_runtime/...`
- `tests_unittest/test_team_chat_witness.py`
  - Verifies witness commit hook is called once per agent turn when enabled
- `tests_unittest/test_team_chat_no_side_effects.py`
  - Verifies flags-off multi-agent mode exits non-zero with no file writes and no commits
- `tests_unittest/test_policy_router_teamchat_intent.py`
  - Verifies `teamchat:<agent>` intents route and consume budget via configured fallback intent key

## Commands Run + Outcomes

- `python3 -m unittest -q tests_unittest.test_team_chat_basic tests_unittest.test_team_chat_witness tests_unittest.test_team_chat_no_side_effects tests_unittest.test_policy_router_teamchat_intent tests_unittest.test_team_chat_autocommit_contract`
  - `Ran 8 tests ... OK`
- `bash workspace/scripts/verify_team_chat.sh`
  - `ok`
- `python3 -m unittest -q`
  - `Ran 147 tests ... OK`
- `npm test --silent`
  - `OK 38 test group(s)`
- `python3 workspace/scripts/verify_goal_identity_invariants.py`
  - exit `0`

## Known Limitations (v1)

- Multi-agent orchestration is deterministic round-robin only (no advanced planner/critic branching).
- Transport is CLI-only in this change set (no Discord/Telegram integration).
- Agent prompts currently use recent transcript window; no long-horizon summarization in this layer.
