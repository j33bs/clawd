# Outbound Sanitizer Globalization + Telegram Reply Mode

- Date (UTC): 2026-02-25T23:58:43Z
- Branch: `codex/fix/dali-audit-hardening-mcp-client-20260226`

## Scope
Implemented a shared outbound sanitization boundary in runtime hardening and applied it at the global fetch choke point used by chat adapters.

## Channels Hardened
Outbound payload sanitization now runs (by endpoint classification) for:
- Telegram Bot API send/edit media/text endpoints
- Discord API webhook/channel message endpoints
- Slack `chat.postMessage` / `chat.update` endpoints
- Mattermost `/api/v4/posts`
- Microsoft Teams webhook/message endpoints

Sanitization behavior:
- strips internal sections (`Reasoning:`, `Analysis:`, `Plan:`, `Thoughts:`, `Chain-of-thought:`, `Scratchpad:`)
- strips `<analysis>`, `<think>`, and ```analysis blocks
- normalizes whitespace
- applies channel length limits
- enforces non-empty fallback text when output is empty/legacy sentinel
- emits structured log events for `STRIPPED_INTERNAL` and `EMPTY_OR_STRIPPED`

## Telegram Reply Mode
Added runtime hardening config knob:
- `TELEGRAM_REPLY_MODE=never|auto|always`
- default: `never`

Semantics:
- `never`: strips `reply_to_message_id` and `reply_parameters` before send
- `always`: preserves reply threading fields
- `auto`: replies only for command-like inbound text hints (`/cmd` or `word:` patterns)

## Commands + Outputs

### Discovery
```bash
rg -n "sendMessageTelegram|api\.sendMessage|/sendMessage|reply_to_message_id|reply_parameters" -S .runtime/openclaw/dist/send-*.js | sed -n '1,24p'
```
```text
.runtime/openclaw/dist/send-Bwxyans7.js:1271: sendMessageTelegram: () => sendMessageTelegram,
.runtime/openclaw/dist/send-Bwxyans7.js:1375: if (params.quoteText?.trim()) threadParams.reply_parameters = {
.runtime/openclaw/dist/send-Bwxyans7.js:1379: else threadParams.reply_to_message_id = replyToMessageId;
.runtime/openclaw/dist/send-Bwxyans7.js:1461:async function sendMessageTelegram(to, text, opts = {}) {
.runtime/openclaw/dist/send-Bwxyans7.js:1517: ... api.sendMessage(chatId, htmlText, sendParams)
.runtime/openclaw/dist/send-Bwxyans7.js:1520: ... api.sendMessage(chatId, fallbackText ?? rawText, plainParams)
... (additional hashed send bundles)
```

```bash
rg -n "discord\.com|chat\.postMessage|mattermost|teams\.microsoft\.com|slack\.com/api/chat\.postMessage" -S .runtime/openclaw/dist/send-*.js | sed -n '1,24p'
```
```text
.runtime/openclaw/dist/send-DwdhCvgE.js:134:const DISCORD_API_BASE = "https://discord.com/api/v10";
.runtime/openclaw/dist/send-DwdhCvgE.js:1825: const baseUrl = new URL(`https://discord.com/api/v10/webhooks/...`)
.runtime/openclaw/dist/send-BH9aKRhH.js:278: ... params.client.chat.postMessage({
... (additional hashed send bundles)
```

```bash
rg -n "classifyOutboundChannel|telegramReplyMode|buildTelegramSendPayload|sanitizeOutboundPayload" -S workspace/runtime_hardening/overlay/runtime_hardening_overlay.mjs
```
```text
11:  sanitizeOutboundPayload,
12:  buildTelegramSendPayload
18:function classifyOutboundChannel(url) {
66:  const sanitized = sanitizeOutboundPayload(payload, {
79:    const modeApplied = buildTelegramSendPayload({
81:      mode: context.config.telegramReplyMode
91:        mode: context.config.telegramReplyMode,
207:    const channel = classifyOutboundChannel(requestUrl);
```

### Verification
```bash
npm run typecheck:hardening
```
```text
> openclaw@0.0.0 typecheck:hardening
> node --check workspace/runtime_hardening/src/*.mjs && node --check workspace/runtime_hardening/src/security/*.mjs && node --check workspace/runtime_hardening/overlay/*.mjs
```

```bash
npm run test:hardening
```
```text
> openclaw@0.0.0 test:hardening
> node --test workspace/runtime_hardening/tests/*.test.mjs
...
# tests 9
# pass 9
# fail 0
```

```bash
npm run runtime:rebuild
```
```text
> openclaw@0.0.0 runtime:rebuild
> bash workspace/scripts/rebuild_runtime_openclaw.sh
repo_sha=b43e5e1
marker_check_runtime_dist:
.../dist/index.js:2:import "./runtime_hardening_overlay.mjs";
.../dist/hardening/config.mjs:102:    throw new Error(`Invalid runtime hardening configuration:\n- ${errors.join('\n- ')}`);
.../dist/runtime_hardening_overlay.mjs:290:  runtimeLogger.info('runtime_hardening_initialized', {
```

## Commits
- `18a8e71` fix(outbound): centralize sanitizer and empty fallback primitives
- `0bd80fe` fix(telegram): default no reply threading and wire global outbound choke point
- `b43e5e1` test(outbound,telegram): cover sanitizer fallback and reply mode payload rules

## Rollback
Revert in reverse order:
1. `git revert b43e5e1`
2. `git revert 0bd80fe`
3. `git revert 18a8e71`

## Known Limitations
- Manual live-chat smoke (actual Telegram command/non-command messages) was not executed in this pass; deterministic payload tests cover mode logic.
- `auto` mode depends on available inbound text hint fields. If hints are absent, it defaults to non-reply behavior.
