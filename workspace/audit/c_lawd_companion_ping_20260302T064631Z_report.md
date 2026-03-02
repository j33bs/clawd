# C_LAWD Companion Ping Contract Endpoint — Implementation Report

## Purpose
Implement a minimal, reversible, evidence-backed contract endpoint on C_LAWD gateway:
- `GET /companion/ping?message_id=<id>&from=<node>` with strict validation
- traceable `contract_signal` emission via existing telemetry sink
- deterministic tests for happy path and invalid `message_id`

## Acceptance Criteria
1. Valid request returns `200` JSON with required fields.
2. Invalid `message_id` returns `400` with `{"ok":false,"error":"invalid_message_id"}`.
3. Emits traceable event type `contract_signal` without logging secrets.
4. Evidence bundle + report captured under `workspace/audit/_evidence/...` and `workspace/audit/..._report.md`.

## Baseline / Preflight Evidence
Evidence dir: `workspace/audit/_evidence/c_lawd_companion_ping_20260302T064631Z`

Captured before edits:
- `pre_git_status_porcelain.txt`
- `pre_git_branch_head.txt`
- `pre_node_npm_versions.txt`
- `pre_openclaw_gateway_status.txt`
- `pre_tailscale_serve_status.txt`
- `router_search.txt`

Notes:
- `tailscale serve status` check did not return mapping and reported: `The Tailscale CLI failed to start: Failed to load preferences.`
- Serve mapping therefore could not be confirmed in this run; no serve config changes were made.

## Gateway Insertion Point
Routing/edge server identified in:
- `scripts/system2_http_edge.js`

This module already owns:
- route policy decisions
- auth enforcement (Bearer/HMAC)
- audit/telemetry sink writes via `audit(...)`

Assumption used for this tranche:
- Contract surface is implemented at the repo-owned HTTP edge layer. If current runtime traffic is routed directly to a different gateway process on `127.0.0.1:18789`, deployment wiring will need to route through this edge for `/companion/ping` to be externally observable.

## Changes Made
1. `scripts/system2_http_edge.js`
- Added token validator for companion params using regex `^[A-Za-z0-9._:-]+$`.
- Added `/companion/ping` route policy for `GET` and `OPTIONS`.
- Added request parsing/validation:
  - `message_id` required, trim, length 8..128, regex match
  - invalid -> `400 {"ok":false,"error":"invalid_message_id"}`
  - `from` optional; if provided invalid -> `"invalid"`; if omitted/blank -> `"unknown"`
- Added successful response payload:
  - `{ ok, message_id, from, to:"c_lawd", node:"c_lawd", ts }`
- Emitted native telemetry event through existing sink:
  - `event_type: "contract_signal"`
  - includes `message_id`, `from`, `to`, `node`, `route`

2. `tests/companion_ping.test.js` (new)
- Deterministic happy-path test:
  - asserts `200`, required response fields, ISO timestamp
  - asserts `contract_signal` event appears in captured logs
- Deterministic invalid-id test:
  - `/companion/ping?message_id=bad!!` -> `400` with exact error payload

## Commands Run + Exit Codes
Preflight and discovery outputs are in evidence files listed above.

Test commands:
1. `node tests/companion_ping.test.js`
- Exit code: `0`
- Evidence: `test_companion_ping_cmd.txt`, `test_companion_ping_stdout.txt`, `test_companion_ping_stderr.txt`

2. `node tests/system2_http_edge.test.js`
- Exit code: `0`
- Evidence: `test_system2_http_edge_cmd.txt`, `test_system2_http_edge_stdout.txt`, `test_system2_http_edge_stderr.txt`

Git/packaging:
1. `git checkout -b codex/feat/c_lawd-companion-ping-20260302` (sandbox)
- Exit code: `128`
- Evidence: `branch_create_attempt.txt`
- Error: `cannot lock ref ... Operation not permitted`

2. Same git branch/create/commit steps executed in elevated command context (no sudo)
- Exit code: `0`
- Evidence: `branch_create_escalated.txt`, `git_add.txt`, `git_commit.txt`

## Ref-Lock Classification + Remediation
Classification: sandbox restriction on `.git` ref lock writes (not repository corruption).

Remediation applied:
- Re-ran git branch/create/commit in execution context that can write `.git` internals.
- No ownership/permission mutations, no destructive operations.

## Branch and Commit
- Branch: `codex/feat/c_lawd-companion-ping-20260302`
- Commit: `240fb5f12f160c679e698224f6fa8b86f5d9bf32`
- Commit message: `feat(companion): add /companion/ping contract endpoint + tests`

Patch artifacts:
- `final_commit_show_stat.txt`
- `final_patch.diff`
- `post_git_status_porcelain.txt`

## Changed Files
- `scripts/system2_http_edge.js`
- `tests/companion_ping.test.js`

## Manual Verification Commands
Local gateway:
```bash
curl -sS "http://127.0.0.1:18789/companion/ping?message_id=test12345&from=dali"
```

Tailnet Serve URL:
```bash
curl -sk "https://heath-macbook.tail5e5706.ts.net/companion/ping?message_id=test12345&from=dali"
```

If your deployment path enforces gateway/edge auth, include the existing bearer header used by your control surface:
```bash
curl -sS -H "Authorization: Bearer <existing-token>" "http://127.0.0.1:18789/companion/ping?message_id=test12345&from=dali"
```

Expected successful response shape:
```json
{
  "ok": true,
  "message_id": "test12345",
  "from": "dali",
  "to": "c_lawd",
  "node": "c_lawd",
  "ts": "<ISO8601>"
}
```

Invalid message id example:
```bash
curl -sS "http://127.0.0.1:18789/companion/ping?message_id=bad!!&from=dali"
```
Expected:
```json
{"ok":false,"error":"invalid_message_id"}
```

## Safety / Reversibility
- No auth guard weakened.
- No control UI/security policy changes.
- No network bind changes (gateway logic remains loopback-bound by default).
- Revert by resetting this commit or removing changed files in this branch.
