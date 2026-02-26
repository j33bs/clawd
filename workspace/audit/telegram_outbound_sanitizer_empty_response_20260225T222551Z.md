# Telegram Outbound Sanitizer + Empty Response Guard

- UTC timestamp: 2026-02-25T22:25:51Z
- Branch: `codex/fix/dali-audit-hardening-mcp-client-20260226`
- Scope: Stop user-visible reasoning leakage and empty fallback leakage at final Telegram outbound boundary

## A) Code Path Discovery

### 1) Locate `No response generated. Please try again.`

Command (requested):
```bash
rg -n "No response generated\. Please try again\." -S .
```

Output:
```text
./workspace/runtime_hardening/src/telegram_outbound_sanitize.mjs:4:const LEGACY_EMPTY_RESPONSE = 'No response generated. Please try again.';
./workspace/runtime_hardening/tests/telegram_outbound_sanitize.test.mjs:26:  assert.equal(payload.text.includes('No response generated. Please try again.'), false);
```

Hidden runtime dist scan (actual upstream source of fallback constants):
```bash
rg -n --hidden -g '!.git' "No response generated\. Please try again\." -S .runtime/openclaw/dist
```

```text
.runtime/openclaw/dist/plugin-sdk/reply-YQvtZDnf.js:48295:const EMPTY_RESPONSE_FALLBACK$1 = "No response generated. Please try again.";
.runtime/openclaw/dist/plugin-sdk/reply-YQvtZDnf.js:48855:const EMPTY_RESPONSE_FALLBACK = "No response generated. Please try again.";
.runtime/openclaw/dist/pi-embedded-BfJSmJ1k.js:66509:const EMPTY_RESPONSE_FALLBACK$1 = "No response generated. Please try again.";
.runtime/openclaw/dist/pi-embedded-BfJSmJ1k.js:67069:const EMPTY_RESPONSE_FALLBACK = "No response generated. Please try again.";
.runtime/openclaw/dist/reply-Cx57rl6c.js:43752:const EMPTY_RESPONSE_FALLBACK$1 = "No response generated. Please try again.";
.runtime/openclaw/dist/reply-Cx57rl6c.js:44312:const EMPTY_RESPONSE_FALLBACK = "No response generated. Please try again.";
.runtime/openclaw/dist/pi-embedded-BDhvoWGL.js:66511:const EMPTY_RESPONSE_FALLBACK$1 = "No response generated. Please try again.";
.runtime/openclaw/dist/pi-embedded-BDhvoWGL.js:67071:const EMPTY_RESPONSE_FALLBACK = "No response generated. Please try again.";
.runtime/openclaw/dist/subagent-registry-DAeKcITJ.js:59676:const EMPTY_RESPONSE_FALLBACK$1 = "No response generated. Please try again.";
.runtime/openclaw/dist/subagent-registry-DAeKcITJ.js:60236:const EMPTY_RESPONSE_FALLBACK = "No response generated. Please try again.";
```

### 2) Locate `Reasoning:`

Command (requested):
```bash
rg -n "Reasoning:" -S workspace src . || true
```

Output:
```text
rg: src: No such file or directory (os error 2)
workspace/runtime_hardening/tests/telegram_outbound_sanitize.test.mjs:11:  const input = 'Hello\n\nReasoning:\n<stuff>';
workspace/runtime_hardening/tests/telegram_outbound_sanitize.test.mjs:14:  assert.equal(out.includes('Reasoning:'), false);
workspace/runtime_hardening/tests/telegram_outbound_sanitize.test.mjs:33:    text: 'Reasoning:\nonly internal'
workspace/runtime_hardening/tests/telegram_outbound_sanitize.test.mjs:38:  assert.equal(payload.text.includes('Reasoning:'), false);
```

Hidden runtime dist scan:
```bash
rg -n --hidden -g '!.git' "Reasoning:" -S .runtime/openclaw/dist | sed -n '1,120p'
```

Output includes reply/send modules with reasoning markers, including:
```text
.runtime/openclaw/dist/reply-Cx57rl6c.js:43665:const REASONING_MESSAGE_PREFIX = "Reasoning:\n";
.runtime/openclaw/dist/plugin-sdk/reply-YQvtZDnf.js:48208:const REASONING_MESSAGE_PREFIX = "Reasoning:\n";
.runtime/openclaw/dist/pi-embedded-BfJSmJ1k.js:66422:const REASONING_MESSAGE_PREFIX = "Reasoning:\n";
.runtime/openclaw/dist/subagent-registry-DAeKcITJ.js:59589:const REASONING_MESSAGE_PREFIX = "Reasoning:\n";
```

### 3) Telegram send boundary (final choke point)

```bash
rg -n "async function sendMessageTelegram\(|telegram/send|api\.sendMessage\(" -S .runtime/openclaw/dist/send-*.js
```

```text
.runtime/openclaw/dist/send-WED6JSOM.js:1849:async function sendMessageTelegram(to, text, opts = {}) {
.runtime/openclaw/dist/send-WED6JSOM.js:1905: ... api.sendMessage(chatId, htmlText, sendParams)
.runtime/openclaw/dist/send-WED6JSOM.js:1908: ... api.sendMessage(chatId, fallbackText ?? rawText, plainParams)
```

## B) Implementation

Implemented a single outbound sanitizer helper and fetch-level Telegram boundary patch in runtime overlay:

- `workspace/runtime_hardening/src/telegram_outbound_sanitize.mjs`
  - `sanitizeOutboundText(text)`
  - strips internal prefixes/tags (`Reasoning`, `Analysis`, `Plan`, `Thoughts`, `Chain-of-thought`, `Scratchpad`, `<analysis>`, `<think>`, ```analysis)
  - drops content from first internal prefix/tag to end-of-message
  - trims/collapses excessive blank lines
  - truncates to Telegram-safe length (4096)
  - treats legacy empty text (`No response generated. Please try again.`) as empty
- `workspace/runtime_hardening/overlay/runtime_hardening_overlay.mjs`
  - installs `fetch` interceptor for Telegram `sendMessage`-style endpoints
  - sanitizes outbound text/caption payloads at final boundary
  - if sanitized result is empty, sends safe fallback:
    - `I didn't generate a reply that time. If you mean the list from yesterday, I can regenerate it: top 10 or full list?`
  - emits structured logs with:
    - `reason=EMPTY_OR_STRIPPED_RESPONSE`
    - `correlation_id`
    - `chat_id`
    - `message_id`

## C) Best-effort upstream check

Searched runtime modules for explicit user-facing concatenation of `answer + "\n\nReasoning:" + internalReason`.
No direct concatenation pattern found in tracked workspace source files; runtime dist contains separate reasoning-mode paths.
Boundary sanitization remains the enforceable protection for Telegram user replies.

## D) Deterministic Tests Added

- `workspace/runtime_hardening/tests/telegram_outbound_sanitize.test.mjs`
  1. reasoning leak strip: `Hello\n\nReasoning:\n...` -> `Hello`
  2. empty response fallback (blank input)
  3. stripped-to-empty fallback (`Reasoning:\nonly internal`)

## E) Verification Commands + Outputs

### Hardening typecheck
```bash
npm run typecheck:hardening
```
```text
> openclaw@0.0.0 typecheck:hardening
> node --check workspace/runtime_hardening/src/*.mjs && node --check workspace/runtime_hardening/src/security/*.mjs && node --check workspace/runtime_hardening/overlay/*.mjs
```

### Hardening tests
```bash
npm run test:hardening
```
```text
# tests 7
# pass 7
# fail 0
```

### Targeted new test (spec)
```bash
node --test --test-reporter=spec workspace/runtime_hardening/tests/telegram_outbound_sanitize.test.mjs
```
```text
✔ workspace/runtime_hardening/tests/telegram_outbound_sanitize.test.mjs
ℹ pass 1
ℹ fail 0
```

### Runtime rebuild with overlay marker
```bash
npm run runtime:rebuild
```
```text
repo_sha=b0d0ff5
marker_check_runtime_dist:
/home/jeebs/src/clawd/.runtime/openclaw/dist/index.js:2:import "./runtime_hardening_overlay.mjs";
/home/jeebs/src/clawd/.runtime/openclaw/dist/runtime_hardening_overlay.mjs:163:  runtimeLogger.info('runtime_hardening_initialized', {
```

### Overlay patch marker check
```bash
rg -n "telegram_outbound_fetch_sanitizer_installed|telegram_outbound_empty_or_stripped_response|sanitizeTelegramOutboundPayload" -S \
  .runtime/openclaw/dist/runtime_hardening_overlay.mjs \
  .runtime/openclaw/dist/hardening/telegram_outbound_sanitize.mjs
```
```text
.runtime/openclaw/dist/runtime_hardening_overlay.mjs:126:  runtimeLogger.info('telegram_outbound_fetch_sanitizer_installed');
.runtime/openclaw/dist/hardening/telegram_outbound_sanitize.mjs:92:    options.logger.error('telegram_outbound_empty_or_stripped_response', {
```

## F) Rollback

- Revert fix/test commits for this change in reverse order after listing branch deltas:
```bash
git rev-list --reverse --oneline origin/main..HEAD
git revert $(git rev-list --reverse origin/main..HEAD)
```
