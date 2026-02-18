# Codex Task List - Issues Beyond My Reach

## 🔴 Critical (Breaking)

### 1. Auth Profile Path Mismatch
- **Issue:** Some agents looking in `.clawdbot/` instead of `.openclaw/`
- **Evidence:** `Auth store: /Users/heathyeager/.clawdbot/agents/main/agent/auth-profiles.json`
- **Fix:** Update agent config to use correct openclaw path, or copy auth-profiles

### 2. Missing API Keys (Groq + Ollama)
- **Issue:** `No API key found for provider "groq"` and `"ollama"`
- **Evidence:** Gateway logs show auth failures for fallback providers
- **Fix:** Either:
  - Add API keys to auth profiles, OR
  - Remove groq/ollama from fallback chain (if not needed)

### 3. Provider Rate Limits
- **Issue:** `google-gemini-cli` and `qwen-portal` in cooldown (rate_limit)
- **Fix:** Wait for cooldown to expire OR adjust rate limits

---

## 🟡 Medium Priority

### 4. Router Module Path Error
- **Issue:** `Cannot find module '/Users/heathyeager/clawd/core/router.js'`
- **Actual location:** `core/system2/inference/router.js`
- **Fix:** Update require() paths in dependent files

### 5. Embedded Agent Tool Call Error
- **Issue:** `read tool called without path`
- **Evidence:** `toolCallId=call_function_nwdgv8gl7oup_1 argsType=object`
- **Fix:** Investigate embedded agent tool invocation

---

## 🟢 Low Priority / TODO

### 6. Daily Briefing Check
- Verify cron job `15f0bbc8-e726-4426-ac15-e9deb9778318` firing at 7 AM

### 7. HiveMind Phase 3 Testing
- Run scan-contradictions, prune --dry-run, digest commands
- Already tested: query tool works ✅

### 8. Wim Hof App Research
- 2-month goal: research AI enhancements for existing app

### 9. vLLM Metal Server
- Launch local inference with `VLLM_GPU_UTIL=0.40` to prevent OOM

---

## 📋 Quick Commands for Codex

```bash
# Check auth profiles
ls -la ~/.openclaw/agents/main/agent/auth-profiles.json

# Check which agents have wrong path
grep -r ".clawdbot" ~/.openclaw/agents/ 2>/dev/null | head -5

# View rate limit status
openclaw status --deep

# Test model availability
openclaw models list
```
