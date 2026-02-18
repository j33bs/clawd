# Handoff: C_Lawd Telegram + WebUI Non-Response Audit (2026-02-18)

## Context
- Audit time: 2026-02-18T10:02:54+10:00 to 2026-02-18T10:26:xx+10:00
- Repo: `/Users/heathyeager/clawd`
- Branch: `codex/task-system2-policy-hardening-cap-20260217`
- Scope: Read-only diagnostics only (no config edits)

## What Was Verified

### 1) Runtime process + ports are up
- `openclaw-gateway` is running (PID observed: `47591`).
- Listening sockets observed:
  - `127.0.0.1:18789` (gateway/control UI)
  - `127.0.0.1:18792` (secondary listener)

### 2) WebUI ingress is reachable
- `curl http://127.0.0.1:18789/` returned `HTTP/1.1 200 OK` and OpenClaw Control UI HTML.
- No reverse proxy (nginx/caddy/traefik) found on `:80/:443`.

### 3) Telegram wiring exists and starts
- `openclaw status --deep` and `openclaw health` report Telegram configured and currently `OK`.
- `openclaw channels list` shows: `Telegram default: configured, token=config, enabled`.

### 4) Load-bearing failures found in gateway logs
Recent `~/.openclaw/logs/gateway.err.log` evidence includes:
- Repeated provider execution failures:
  - `Followup agent failed before reply: All models failed (4)`
- Specific failure reasons in same window:
  - provider cooldown / rate-limit (`google-gemini-cli`, `qwen-portal`)
  - missing API key for fallback providers (`groq`, `ollama`)
- Additional instability during outage window:
  - `TypeError: fetch failed`
  - Telegram send/poll failures (`getUpdates` timeout, `sendMessage failed`)

## Single Most Diagnostic Failure Point
`All models failed (4)` at generation time in gateway runtime.

Interpretation: Telegram and WebUI ingress can be up, but replies still fail when no eligible/authenticated provider path is available at dispatch time.

## Ranked Root Cause Hypotheses
1. **Primary:** No usable model at request time due cooldown/rate-limit + missing fallback provider credentials (`groq`, `ollama`).
2. **Secondary:** Intermittent fetch/network failures worsen reliability (`fetch failed`, Telegram send/poll network failures).
3. **Tertiary:** Local config churn events (`gateway failed: invalid config`) add noise but are not the dominant blocker.

## Smallest Reversible Fix (not applied)
- Temporarily narrow active model primary/fallback set to providers that are currently authenticated + available.
- Remove unavailable fallback providers from active order until credentials/quota are restored.
- Restart gateway once.
- Reversible by restoring previous fallback list from existing `~/.openclaw/openclaw.json.bak*`.

## Regression Checks After Fix
1. `openclaw status --deep` shows gateway reachable and Telegram `OK`.
2. WebUI request gets a real reply (not stuck/no-response).
3. Telegram ping gets a reply.
4. `gateway.err.log` has no new `All models failed`, no new `sendMessage failed` for 5+ minutes under light traffic.
5. `openclaw health` remains healthy.

## Notes
- Sensitive values were intentionally redacted in this audit narrative.
- This handoff preserves the evidence trail and recommended next action without applying changes.
