# Clawdbot Troubleshooting Session

## Issue
Agent (@Claudiajeebsbot) not responding to Telegram messages after authorization.

## Environment
- OS: macOS 26.2 (arm64)
- Node: 25.4.0
- Clawdbot version: 2026.1.24-3
- Working directory: /Users/heathyeager/clawd

## Current Status (as of 2026-01-29 13:30)

### What's Working ✓
- Gateway running (PID 3480) on ws://127.0.0.1:18789
- Telegram channel connected (@Claudiajeebsbot)
- Model configured: anthropic/claude-sonnet-4-5 (shows as "configured" with auth)
- clawdbot processes running (clawdbot + clawdbot-gateway)
- `/login` command successful in Claude Code CLI

### What's NOT Working ✗
- Agent not responding to Telegram messages
- Agent stuck in "bootstrapping" state

## Investigation Findings

### 1. Process Status
```bash
ps aux | grep clawd
# Shows:
# - clawdbot (PID 3479)
# - clawdbot-gateway (PID 3480)
```

### 2. Doctor Output
```bash
clawdbot doctor
# Shows:
# - Telegram: ok (@Claudiajeebsbot)
# - Agents: main (default)
# - Agent state: "1 bootstrapping"
# - Session store: 1 entries, last activity 12m ago
```

### 3. Config Check
- Auth profile: "anthropic:manual" mode "token"
- API key NOT found at path `anthropic.apiKey`
- Model shows "Local Auth: yes" and tags include "configured"
- No anthropic credentials file in ~/.clawdbot/credentials/

### 4. Log Errors
Gateway error log shows repeated:
```
TypeError: fetch failed
at node:internal/deps/undici/undici:16416:13
```

### 5. Agent State
- Status shows: "1 bootstrapping"
- BOOTSTRAP.md exists in workspace
- Agent waiting for initial identity setup conversation

## Theories

### Theory 1: Bootstrap State Block
- Agent won't respond until bootstrap conversation completes
- Bootstrap requires agent to respond first (catch-22?)

### Theory 2: API Auth Issue
- Fetch errors suggest API calls failing
- `clawdbot config get anthropic.apiKey` returns "not found"
- But model shows as "configured" - credentials stored elsewhere?

### Theory 3: Missing Credentials
- User ran `/login` in Claude Code CLI (successful)
- May need separate auth for clawdbot agent
- Credentials might be in keychain/environment, not files

## SOLUTION FOUND ✅

**Root Cause:** Pending Telegram pairing request not approved

When you first message the bot on Telegram, it creates a pairing request that must be manually approved before the bot will respond.

**Fix:**
```bash
# 1. List pending pairing requests
clawdbot pairing list telegram

# 2. Approve the request using the code shown
clawdbot pairing approve telegram <CODE>
```

**Applied Fix:**
```bash
clawdbot pairing approve telegram SGNJY7GE
# Result: Approved telegram sender 8159253715
```

Bot should now respond to Telegram messages!

## Additional Issues Found via Web Search

### Fetch Errors (TypeError: fetch failed)
The fetch errors in the logs are a known issue:
- **Node 22 bug**: Fetch timeouts with Telegram API (fixed in Node 25.x ✓)
- **IPv6 issues**: api.telegram.org resolves to IPv6 first, causing timeouts
- **Workaround**: `NODE_OPTIONS=--dns-result-order=ipv4first`

Sources:
- [Node 22 fetch timeout issue](https://github.com/moltbot/moltbot/issues/2436)
- [Unhandled promise rejections](https://github.com/moltbot/moltbot/issues/2879)
- [ClawdBot setup guide](https://lukasniessen.medium.com/clawdbot-setup-guide-how-to-not-get-hacked-63bc951cbd90)

## Questions Answered
- ✓ Pairing approval required after first message
- ✓ Bootstrap state doesn't block responses once paired
- ✓ Fetch errors are transient network issues (non-blocking)
- ✓ Authentication was properly configured all along

## Telegram Token / Webhook Diagnostics (Secret-Safe)

Use repo-local diagnostics (never prints token value):

```bash
node scripts/telegram_diag.js
```

Outputs:
- token length
- has whitespace/quotes/newline flags
- `getMe` HTTP status + truncated response preview
- `getWebhookInfo` HTTP status + webhook set/unset

If polling is expected and webhook is set, reset webhook without dropping updates:

```bash
node scripts/telegram_diag.js --reset-webhook
```

To explicitly drop pending updates (opt-in only):

```bash
node scripts/telegram_diag.js --reset-webhook --drop-pending
```

## macOS LaunchAgent Environment Mismatch

Interactive shell env vars do not automatically propagate into LaunchAgent services.

Practical check:
- `launchctl list | grep -i openclaw`
- Inspect `~/Library/LaunchAgents/ai.openclaw.gateway.plist` `EnvironmentVariables`

If Telegram works in shell but not service, configure token through OpenClaw config (preferred) or service environment, then reload service:

```bash
openclaw gateway restart
```
