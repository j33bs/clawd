# Next Actions — System2 Bot Restore

## Root Cause

**Two concurrent failures:**

1. **LLM auth cascade (PRIMARY)**: All 4 free-tier providers in `free_order` have broken/expired credentials in `~/.openclaw/agents/main/agent/auth-profiles.json`. When a Telegram message arrives, the agent tries all 4 providers, all fail with auth errors, and the bot cannot generate a reply.

2. **Telegram polling degradation (SECONDARY)**: `getUpdates` long-poll requests are timing out every ~20 minutes for 8+ hours. The gateway retries (good), but the connection never fully recovers. A gateway restart will clear this.

## Fix Steps (in order)

### Step 1: Re-authenticate free LLM providers

The fastest path is to re-auth Google Gemini (slot 1 in free_order):

```bash
openclaw auth login google-gemini-cli
```

This opens a browser OAuth flow. Complete it. Then verify:

```bash
openclaw auth status
```

You should see `google-gemini-cli: authenticated` with a valid token.

### Step 2: Create the missing Ollama auth profile

Ollama doesn't need a real API key, but the gateway requires a profile entry. Fix:

```bash
openclaw auth add ollama --type none
```

If that doesn't work, the fallback is:

```bash
openclaw models test ollama/qwen2.5-coder:7b
```

### Step 3: Restart the gateway (clears stale Telegram polling)

```bash
openclaw gateway restart
```

This clears the stale `getUpdates` connections and re-establishes Telegram polling.

### Step 4: Verify end-to-end

```bash
# Gateway + Telegram health
openclaw status --deep

# LLM routing test
openclaw models test google-gemini-cli/gemini-3-pro-preview

# Ollama local test
openclaw models test ollama/qwen2.5-coder:7b

# Send a test message from Telegram and watch logs
tail -f ~/.openclaw/logs/gateway.err.log
```

### Optional: Re-auth remaining providers

These are lower priority (Gemini + Ollama should be sufficient):

```bash
# Qwen Portal (free, slot 2)
openclaw auth login qwen-portal

# Groq (free, slot 3) — needs API key from console.groq.com
openclaw auth add groq --api-key <your-groq-key>
```

## Rollback

If the gateway restart causes issues:

```bash
# The gateway is a LaunchAgent — it auto-restarts
# To force stop:
openclaw gateway stop

# To restore from backup config:
cp ~/.openclaw/openclaw.json.bak ~/.openclaw/openclaw.json
openclaw gateway restart
```

Auth profile backups exist at:
- `~/.openclaw/agents/main/agent/auth-profiles.json.bak-*`

## Why This Happened

1. **OAuth tokens expired** — Google Gemini CLI and Qwen Portal use OAuth, which expires. No auto-refresh was triggered.
2. **Groq API key was never set** — the profile exists but has no `apiKey` value.
3. **Ollama profile never created** — the routing order references `ollama:default` but the profile was never added to `auth-profiles.json`.
4. **Telegram polling degradation** — likely a side-effect of the gateway running for extended periods with failing LLM calls. The TCP connection to Telegram's API may have been disrupted by system sleep/wake or network change.
