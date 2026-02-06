# DESIGN_MODEL_ROUTER_STEP_B.md

Date: 2026-02-06
Stage: Step B Design Brief (doc-only, no behavior changes)

## A) Problem Statement and Non-Goals

### Problem statement
OpenClaw repository code currently lacks a canonical model-call entrypoint. Existing fallback logic in `scripts/multi_agent_fallback.js` is credit-threshold oriented and has a stubbed `makeRequest(...)` path. We need a design for deterministic model routing with explicit governance logging and failover behavior:
- Preferred: Oath Claude when healthy.
- If Oath unhealthy/limited: Anthropic Claude API for non-basic tasks.
- BASIC tasks: Local Qwen by default unless explicitly marked `requires_claude=true`.

### Non-goals (this step)
- No runtime wiring.
- No behavioral change.
- No provider client implementation.
- No mutation of existing fallback scripts beyond future migration plan.

## B) Canonical Entrypoint Definition

### New canonical module (planned)
`core/model_call.js`

### Exported function (single entrypoint)
```js
async function callModel({
  taskId,
  messages,
  taskClass,
  requiresClaude,
  allowNetwork,
  preferredBackend,
  metadata
}) => {
  // returns { backend, response, usage, events }
}
```

### Input contract
- `taskId`: string (required; generate if absent upstream).
- `messages`: array of internal message objects (required).
- `taskClass`: `BASIC | NON_BASIC | undefined`.
- `requiresClaude`: boolean (default `false`).
- `allowNetwork`: boolean (default `true` for remote providers, required `false` for local-only runs).
- `preferredBackend`: optional enum override.
- `metadata`: optional small object (`task_name`, `source`, `requires_claude`, etc.).

### Output contract
```js
{
  backend: 'OATH_CLAUDE' | 'ANTHROPIC_CLAUDE_API' | 'LOCAL_QWEN',
  response: { text, raw },
  usage: { inputTokens, outputTokens, totalTokens, estimatedCostUsd },
  events: [/* governance events emitted during routing/call */]
}
```

## C) Router Decision Table and Override Semantics

### Backend precedence
- `BASIC`:
  - `requires_claude=true` -> `OATH_CLAUDE` if healthy, else `ANTHROPIC_CLAUDE_API`, else `LOCAL_QWEN`.
  - otherwise -> `LOCAL_QWEN`.
- `NON_BASIC`:
  - `OATH_CLAUDE` if healthy, else `ANTHROPIC_CLAUDE_API`, else `LOCAL_QWEN` (last resort + warning event).

### Overrides
- `preferredBackend`:
  - advisory only unless compatible with policy.
  - cannot force remote backend when `allowNetwork=false`.
- `requires_claude`:
  - hard override against BASIC default Qwen behavior.
- `allowNetwork=false`:
  - force `LOCAL_QWEN` and emit `ROUTE_SELECT` rationale `network_disallowed`.

### Task classification source of truth
1. explicit metadata first (`taskClass` or `metadata.task_class`).
2. heuristic fallback second (phase 2 classifier):
   - BASIC heuristics: file search/listing/format/lint/docs edits/small refactors/local summarization/test/build reporting.
   - NON_BASIC heuristics: architecture/governance, multi-file invariant refactors, deep debugging, explicit `requires_claude`.

## D) Provider Interface Contracts

### Common provider interface
```js
class Provider {
  async call({ messages, maxTokens, temperature, tools, metadata }) {
    // -> { text, raw, usage }
  }

  async health() {
    // -> { ok: boolean, reason?: string, retryAfter?: number }
  }
}
```

### Providers
- `OathClaudeProvider`
  - wraps existing Oath Claude integration surface.
  - includes error normalization wrapper.
- `AnthropicClaudeApiProvider`
  - endpoint: `https://api.anthropic.com/v1/messages`
  - auth: `ANTHROPIC_API_KEY` from env
  - model: `ANTHROPIC_MODEL` (default documented below)
  - required header includes Anthropic API version.
  - retries only for transient errors (TIMEOUT / RATE_LIMIT), max 2 retries with conservative backoff.
- `LocalQwenProvider`
  - wraps existing local Qwen runner/model path.
  - must function with `allowNetwork=false`.

## E) Error Normalization Taxonomy

### Normalized codes
`AUTH | RATE_LIMIT | QUOTA | TIMEOUT | CONTEXT | NETWORK | UNKNOWN`

### Oath mapping (planned)
- HTTP 401, `authentication_error`, `invalid bearer token` -> `AUTH`
- HTTP 429, `rate_limit` -> `RATE_LIMIT`
- `quota_exceeded`, credit exhaustion signal -> `QUOTA`
- transport timeout -> `TIMEOUT`
- `context_length_exceeded` -> `CONTEXT`
- connection/DNS/TLS failure -> `NETWORK`
- otherwise -> `UNKNOWN`

### Anthropic mapping (planned)
- HTTP 401/403 auth failures -> `AUTH`
- HTTP 429 rate limiting -> `RATE_LIMIT`
- quota/billing-limit signals -> `QUOTA`
- request timeout/abort -> `TIMEOUT`
- context window overflow (`context_length_exceeded`) -> `CONTEXT`
- network transport failures -> `NETWORK`
- otherwise -> `UNKNOWN`

## F) Cooldown Policy and Storage

### Cooldown triggers (Oath unhealthy)
- any `AUTH`
- any `RATE_LIMIT` or `QUOTA`
- `TIMEOUT` strike threshold: `>=2` timeouts within rolling `5 minutes`
- any `CONTEXT`

### Defaults
- cooldown duration: `30 minutes`
- timeout strike window: `5 minutes`
- timeout strike threshold: `2`

### State model
```js
{
  oath: {
    disabledUntil: '<ISO timestamp|null>',
    lastError: 'AUTH|RATE_LIMIT|QUOTA|TIMEOUT|CONTEXT|NETWORK|UNKNOWN|null',
    strikeCount: 0,
    lastErrorAt: '<ISO timestamp|null>'
  },
  anthropic: {
    disabledUntil: '<ISO timestamp|null>',
    lastError: '<normalized|null>',
    strikeCount: 0,
    lastErrorAt: '<ISO timestamp|null>'
  }
}
```

### Storage
- Phase 1: in-memory cooldown state in router process.
- Phase 2 (optional persistence): append cooldown snapshots/events to `logs/fallback_events.json` and rebuild transient state on process start.

## G) Governance Logging Schema and Examples

### Reuse existing pattern
Use `scripts/guarded_fs.js` (`resolveWorkspacePath`, `readJsonFile`, `writeJsonFile`) and JSON append files:
- `logs/fallback_events.json`
- `logs/notifications.json`

### Required event types
- `ROUTE_SELECT`
- `BACKEND_ERROR`
- `COOLDOWN_SET`
- `COOLDOWN_CLEAR`

### Required fields (fallback_events.json)
- `event_type`
- `task_id`
- `task_class`
- `from_backend`
- `to_backend`
- `trigger_code` (normalized)
- `provider_error_code` (raw, optional)
- `network_used` (boolean)
- `timestamp` (ISO 8601)
- `rationale` (short machine-readable string)
- `metadata` (optional small object)

### Example: ROUTE_SELECT
```json
{
  "event_type": "ROUTE_SELECT",
  "task_id": "task_123",
  "task_class": "NON_BASIC",
  "from_backend": "OATH_CLAUDE",
  "to_backend": "ANTHROPIC_CLAUDE_API",
  "trigger_code": "RATE_LIMIT",
  "provider_error_code": "429",
  "network_used": true,
  "timestamp": "2026-02-06T01:23:45.000Z",
  "rationale": "oath_unhealthy_fallback_to_anthropic",
  "metadata": { "requires_claude": true }
}
```

### Example: BACKEND_ERROR
```json
{
  "event_type": "BACKEND_ERROR",
  "task_id": "task_123",
  "task_class": "NON_BASIC",
  "from_backend": "OATH_CLAUDE",
  "to_backend": "OATH_CLAUDE",
  "trigger_code": "AUTH",
  "provider_error_code": "authentication_error",
  "network_used": true,
  "timestamp": "2026-02-06T01:23:40.000Z",
  "rationale": "provider_error",
  "metadata": { "retry": 0 }
}
```

### notifications.json usage
Only user-facing routing notices, e.g.:
- fallback to Qwen due to remote provider unavailability
- network-disabled forcing local backend

Notification shape remains append-only and concise.

## H) Verification Plan (future, not implemented in Step B)

Planned script: `scripts/verify_model_routing.sh` (or `.js`)

Scenarios:
1. BASIC task -> expect `LOCAL_QWEN`.
2. NON_BASIC task with healthy Oath -> expect `OATH_CLAUDE`.
3. Simulate Oath `401` -> expect `ANTHROPIC_CLAUDE_API` and cooldown set.
4. Simulate Oath `429` -> expect `ANTHROPIC_CLAUDE_API` and cooldown set.
5. Simulate repeated Oath timeouts (2 within window) -> expect Anthropic and cooldown.
6. Simulate Anthropic unavailable/missing `ANTHROPIC_API_KEY` -> expect `LOCAL_QWEN` with warning notification.

Because current `makeRequest(...)` is stubbed, simulation will use dependency injection/mocks for provider adapters and deterministic mock errors.

PASS criteria:
- expected backend selected for each case
- required governance events appended with required fields
- no silent backend switch (every switch emits event)

## I) Progressive Migration Plan (no big-bang refactor)

### Phase 1
- Add provider adapters + router + `core/model_call.js` and unit tests.
- No integration into existing runtime path yet.

### Phase 2
- Update `scripts/init_fallback_system.js` to instantiate router/providers and export/attach `callModel`.

### Phase 3
- Replace `scripts/multi_agent_fallback.js` `makeRequest(...)` stub to delegate to `callModel(...)`.

### Phase 4
- Enforce governance invariant: all agent model invocations route through `callModel`.
- Add checks/guardrails in verification to detect bypass paths.

## Config Surface (planned)

### Environment variables
- `ANTHROPIC_API_KEY` (required for Anthropic backend)
- `ANTHROPIC_MODEL` (default: `claude-opus-4-5` unless overridden by runtime config)
- `MODEL_ROUTER_COOLDOWN_MINUTES` (default `30`)
- `MODEL_ROUTER_TIMEOUT_WINDOW_MINUTES` (default `5`)
- `MODEL_ROUTER_TIMEOUT_STRIKES` (default `2`)

### Optional config file keys (future)
In `config/agent_fallback.json` (or equivalent runtime config section):
- `router.cooldownMinutes`
- `router.timeoutWindowMinutes`
- `router.timeoutStrikes`
- `router.defaultBasicBackend` (`LOCAL_QWEN`)
- `router.defaultNonBasicBackend` (`OATH_CLAUDE`)

Secrets remain env-only; do not commit credentials.
