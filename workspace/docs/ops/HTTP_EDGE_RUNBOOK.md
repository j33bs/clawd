# System-2 Secure HTTP Edge Runbook

This repo provides an in-repo HTTP edge that fronts the local gateway and enforces:
- Mandatory auth (Bearer tokens, multi-identity)
- Rate limiting per identity
- Request body size limits
- Safe audit logs (no Authorization values, no request bodies)
- Ask-first approval gate for broad actions (deny-by-default)

## What Is Untrusted
All requests arriving via the HTTP edge are treated as **UNTRUSTED** by default.

Untrusted inputs must not directly cause broad actions without explicit approval.

## Start (Foreground)

Set the identity token map (do not commit this; do not log tokens):
```bash
export OPENCLAW_EDGE_TOKENS="heath:<token1>,userA:<token2>"
```

By default the edge binds to loopback only. To bind to a non-loopback address you must explicitly opt in:
```bash
export OPENCLAW_EDGE_BIND="0.0.0.0"
export OPENCLAW_EDGE_BIND_ALLOW_NONLOOPBACK=1
```

Optionally set the upstream gateway token (used only for edge -> gateway forwarding):
```bash
export OPENCLAW_GATEWAY_TOKEN="<gateway-token>"
```

Run:
```bash
node scripts/system2_http_edge.js
```

Defaults:
- Edge bind: `127.0.0.1:18800`
- Upstream: `127.0.0.1:18789`

## Configuration (Env)
- `OPENCLAW_EDGE_BIND` (default `127.0.0.1`)
- `OPENCLAW_EDGE_BIND_ALLOW_NONLOOPBACK` (required when binding non-loopback)
- `OPENCLAW_EDGE_PORT` (default `18800`)
- `OPENCLAW_EDGE_UPSTREAM_HOST` (default `127.0.0.1`)
- `OPENCLAW_EDGE_UPSTREAM_PORT` (default `18789`)
- `OPENCLAW_EDGE_MAX_BODY_BYTES` (default `262144`)
- `OPENCLAW_EDGE_RATE_PER_MIN` (default `30`)
- `OPENCLAW_EDGE_BURST` (default `10`)
- `OPENCLAW_EDGE_TOKENS` (optional if HMAC enabled): `label:token,label2:token2`
- `OPENCLAW_EDGE_HMAC_KEYS` (optional): `keyId:secret,keyId2:secret2`
- `OPENCLAW_EDGE_HMAC_SKEW_SEC` (default `60`)
- `OPENCLAW_EDGE_ALLOW_BEARER_LOOPBACK` (optional): if `1`, allow Bearer auth from loopback when HMAC is enabled
- `OPENCLAW_EDGE_UPSTREAM_TOKEN` (optional): Bearer token to send to upstream
- `OPENCLAW_EDGE_APPROVE_TOKENS` (optional): tokens accepted in `X-OpenClaw-Approve`
- `OPENCLAW_EDGE_AUDIT_PATH` (default `~/.openclaw/audit/edge.jsonl`)
- `OPENCLAW_EDGE_AUDIT_ROTATE_BYTES` (default `10000000`)
- `OPENCLAW_EDGE_AUDIT_ROTATE_KEEP` (default `5`)

## Route Policy (Fail-Closed)
Allowed without approval:
- `GET /health`
- `GET /status`

Requires approval header:
- `POST /rpc/*`
- WebSocket upgrades to `/rpc/*`

Denied:
- Everything else (404)

## Approval Gate (Ask-First)
Broad actions are deny-by-default for untrusted inputs.

Mechanisms:
- Per-request approval header: `X-OpenClaw-Approve: <token>` where `<token>` is in `OPENCLAW_EDGE_APPROVE_TOKENS`

Current behavior (fail-closed):
- Only `POST /rpc/*` requires approval; all other write-like routes are denied.
- WebSocket upgrade requires approval (WebSocket can carry broad RPC) and is only allowed on `/rpc/*`.

## HMAC Mode (Replay Resistant)
If you set `OPENCLAW_EDGE_HMAC_KEYS`, the edge requires signed requests (except optional loopback Bearer when `OPENCLAW_EDGE_ALLOW_BEARER_LOOPBACK=1`).

Headers:
- `X-OpenClaw-Timestamp`: unix seconds
- `X-OpenClaw-KeyId`: key id from `OPENCLAW_EDGE_HMAC_KEYS`
- `X-OpenClaw-Signature`: hex HMAC-SHA256 over:
  - `METHOD + "\\n" + PATH + "\\n" + TIMESTAMP + "\\n" + SHA256_HEX(BODY)`

Notes:
- Never log signatures/keys; treat them as secrets.
- Requests outside the timestamp window are rejected.

## Audit Sink (Append-Only JSONL)
The edge writes metadata-only JSONL audit lines to `OPENCLAW_EDGE_AUDIT_PATH` with size-based rotation.

The audit sink never includes request bodies or `Authorization` values.

## Smoke Tests (No Secrets)
Assume:
- Edge: `http://127.0.0.1:18800`
- Bearer token is set in your environment as `EDGE_TOKEN`

401 without token:
```bash
curl -sS -o /dev/null -w "HTTP=%{http_code}\n" http://127.0.0.1:18800/health
```

200 with token (example):
```bash
curl -sS -o /dev/null -w "HTTP=%{http_code}\n" -H "Authorization: Bearer ${EDGE_TOKEN}" http://127.0.0.1:18800/health
```

429 rate limit (example; requires low limits configured):
```bash
for i in $(seq 1 20); do
  curl -sS -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer ${EDGE_TOKEN}" http://127.0.0.1:18800/health
done
```

413 size limit (requires operator approval or approval header):
```bash
python3 - <<'PY'
import os, requests
token = os.environ.get("EDGE_TOKEN","")
url = "http://127.0.0.1:18800/call"
hdr = {"Authorization": f"Bearer {token}"}
data = "x" * 300000
r = requests.post(url, headers=hdr, data=data.encode("utf-8"))
print("HTTP", r.status_code)
PY
```

## Launchd (Template)
This repo does not install services automatically. Use a LaunchAgent template and keep tokens out of the repo.

Key hardening points:
- Keep upstream gateway loopback-only.
- Bind edge to loopback unless you explicitly need LAN exposure.
- Store tokens via environment injection or a local file read by your launch wrapper (never commit).

Suggested launchd knobs (see `launchd.plist(5)`):
- `KeepAlive` true
- `ThrottleInterval` to avoid tight crash loops
