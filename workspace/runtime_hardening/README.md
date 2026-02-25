# Runtime Hardening Layer

This module set adds deterministic hardening primitives for OpenClaw runtime overlays.

## Modules

- `src/config.mjs`: fail-fast config validation (required `ANTHROPIC_API_KEY`, bounded env knobs)
- `src/session.mjs`: bounded `SessionManager` (TTL eviction, max sessions, history caps)
- `src/mcp_singleflight.mjs`: keyed singleflight lock for MCP server startup
- `src/security/fs_sandbox.mjs`: workspace-root filesystem guardrails
- `src/security/tool_sanitize.mjs`: tool payload shape/size sanitization
- `src/retry_backoff.mjs`: retry with exponential backoff + retry-after support
- `overlay/runtime_hardening_overlay.mjs`: runtime bootstrap overlay for `.runtime/openclaw/dist/index.js`

## Verification

```bash
npm run typecheck:hardening
npm run test:hardening
```

## Runtime Rebuild

```bash
npm run runtime:rebuild
```

The rebuild script copies the upstream OpenClaw runtime to `.runtime/openclaw` and injects:

```js
import "./runtime_hardening_overlay.mjs";
```

into `.runtime/openclaw/dist/index.js` if not already present.
