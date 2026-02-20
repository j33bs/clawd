# Team Chat PR Rollback Note

- Summary: Adds governed multi-agent Team Chat with append-only session logs and policy-routed `teamchat:<agent>` intents. Flags: `OPENCLAW_TEAMCHAT` (default OFF), `OPENCLAW_TEAMCHAT_WITNESS` (default OFF), and existing dual opt-in autocommit signals (`TEAMCHAT_USER_DIRECTED_TEAMCHAT`, `TEAMCHAT_ALLOW_AUTOCOMMIT`).
- Evidence: `workspace/audit/teamchat_implementation_20260220T104111Z.md`

Verification:
- `python3 -m unittest -q`
- `npm test --silent`

Rollback:
- `git revert 73681500f8c730d65ccb7adafe823757e10aa811`
