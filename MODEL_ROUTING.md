# Model Routing

This document describes the Step C model-routing behavior implemented from `DESIGN_MODEL_ROUTER_STEP_B.md`.

## Environment

- `ANTHROPIC_API_KEY`: required for Anthropic Claude API fallback.
- `ANTHROPIC_MODEL`: optional model override for Anthropic fallback.
  - default: `claude-3-5-sonnet-latest`
- `ANTHROPIC_VERSION`: optional Anthropic API version header.
  - default: `2023-06-01`
- `MODEL_ROUTER_COOLDOWN_MINUTES`: cooldown duration in minutes (default `30`).
- `MODEL_ROUTER_TIMEOUT_WINDOW_MINUTES`: timeout strike window in minutes (default `5`).
- `MODEL_ROUTER_TIMEOUT_STRIKES`: timeout strikes before cooldown (default `2`).

## Canonical Entrypoint

- Module: `core/model_call.js`
- Function:

```js
callModel({
  taskId,
  messages,
  taskClass,
  requiresClaude,
  allowNetwork,
  preferredBackend,
  metadata
})
```

Returns:

```js
{
  backend,
  response: { text, raw },
  usage,
  events
}
```

## Routing Summary

- BASIC tasks:
  - `requiresClaude=false` -> `LOCAL_QWEN`
  - `requiresClaude=true` -> `OATH_CLAUDE` -> `ANTHROPIC_CLAUDE_API` -> `LOCAL_QWEN`
- NON_BASIC tasks:
  - `OATH_CLAUDE` -> `ANTHROPIC_CLAUDE_API` -> `LOCAL_QWEN`
- `allowNetwork=false` forces `LOCAL_QWEN`.

Oath cooldown is applied on `AUTH`, `RATE_LIMIT`, `QUOTA`, `CONTEXT`, or timeout strike threshold.

## Governance Events

Uses `scripts/guarded_fs.js` append-json pattern:
- `logs/fallback_events.json`
  - `ROUTE_SELECT`, `BACKEND_ERROR`, `COOLDOWN_SET`, `COOLDOWN_CLEAR`
- `logs/notifications.json`
  - user-facing routing notices only

## Verification

Run:

```bash
npm run verify:model-routing
```

or:

```bash
node scripts/verify_model_routing.js
```

The script simulates:
- BASIC -> Qwen
- NON_BASIC healthy -> Oath
- Oath auth/rate failures -> Anthropic
- Anthropic unavailable/missing key -> Qwen + notification
