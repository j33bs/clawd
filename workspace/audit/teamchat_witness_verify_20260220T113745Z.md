# Team Chat Witness Verification Audit

- UTC: 20260220T113745Z
- Branch: codex/feature/teamchat-witness-docs-and-verify-20260220

## Design notes

- Added deterministic Team Chat witness verification with no default side effects.
- Reused existing witness chain verification from `workspace/scripts/witness_ledger.py` (`verify_chain`) and layered Team Chat consistency checks on top.
- Canonical hash versioning decision:
  - New witness entries use `message_hash_version=teamchat-msg-sha256-v2` and:
    - `sha256(canonical_json({session_id, turn, role, content, route_minimal, ts}))`
  - Verifier preserves compatibility with existing entries by accepting legacy hashes when version is absent/legacy:
    - `teamchat-msg-sha256-legacy`
    - content-only fallback
- Team Chat witness ledger path for Team Chat is runtime-only and ignored:
  - `workspace/state_runtime/teamchat/witness_ledger.jsonl`

## Files changed

- `workspace/teamchat/message.py`
- `workspace/teamchat/orchestrator.py`
- `workspace/teamchat/witness_verify.py`
- `workspace/scripts/team_chat.py`
- `workspace/scripts/verify_teamchat_witness.sh`
- `tests_unittest/test_teamchat_witness_verify.py`
- `workspace/teamchat/README.md`
- `README.md`

## Commands run + outcomes

- `python3 -m unittest -q tests_unittest.test_teamchat_witness_verify tests_unittest.test_team_chat_witness tests_unittest.test_team_chat_basic`
  - `Ran 7 tests ... OK`
- `python3 -m unittest -q`
  - `Ran 152 tests ... OK`
- `npm test --silent`
  - `OK 38 test group(s)`
- `bash workspace/scripts/verify_team_chat.sh`
  - `ok`
- `bash workspace/scripts/verify_teamchat_witness.sh --session verify_teamchat_witness_fixture`
  - `PASS session=verify_teamchat_witness_fixture witnessed_events=2 head_hash=86c931c0fb2320cdfdb59e0756511f562a218cb93a2f763e01408ce45cdbd0bd`

## Reproduce verification

1. Run Team Chat with witness enabled:
   - `OPENCLAW_TEAMCHAT=1 OPENCLAW_TEAMCHAT_WITNESS=1 python3 workspace/scripts/team_chat.py --agents planner,coder --session demo --max-turns 2 --once --message "hello"`
2. Verify witness provenance:
   - `bash workspace/scripts/verify_teamchat_witness.sh --session demo`
3. Optional explicit ledger override:
   - `bash workspace/scripts/verify_teamchat_witness.sh --session demo --ledger workspace/state_runtime/teamchat/witness_ledger.jsonl`
