# Follow-up Scope: Team Chat Test Drift

- Branch: `fix/team_chat-test-drift-20260221`
- Scope: isolate and repair failing TeamChat tests only; no routing/toolcall changes.

## Acceptance Criterion

`python3 -m pytest -q workspace/teamchat/tests`

Pass condition: all tests in `workspace/teamchat/tests` pass.
