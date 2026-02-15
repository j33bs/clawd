# Handoff: Runtime Secrets Auto-Injection + Fail-Closed Env Scoping

Date: 2026-02-16

## Goal
Reduce "dead-provider churn" by ensuring Groq can be configured via the System-2 SecretsBridge in normal runtime (not only via `openclaw secrets exec`), while keeping changes reversible and secret-safe.

## Changes
### 1) System-2 ProviderRegistry: secrets injection is now scoped
File: `/Users/heathyeager/clawd/core/system2/inference/provider_registry.js`

- The registry now **clones** the input env (`{...env}`) and performs SecretsBridge injection into that clone.
- This prevents accidental mutation of the caller env object or `process.env` from inside System-2 inference.

Why: secrets injection should be explicit and instance-scoped inside the System-2 plane.

### 2) OpenClaw secrets plugin: best-effort runtime injection (no `secrets exec` required)
File: `/Users/heathyeager/clawd/scripts/openclaw_secrets_plugin.js`

- When `ENABLE_SECRETS_BRIDGE=1` and the OpenClaw subcommand is one of:
  - `agent`, `gateway`, `daemon`, `dashboard`
  the plugin will **best-effort inject** secrets into the running OpenClaw process env using `SecretsBridge.injectRuntimeEnv(process.env)`.
- Opt-out: `OPENCLAW_SYSTEM2_SECRETS_AUTO_INJECT=0`
- Also sets a harmless sentinel `OLLAMA_API_KEY=ollama` if missing, so local Ollama can remain eligible in runtimes that treat missing keys as fatal.

No secret values are printed.

## Evidence (safe)
1) Without bridge:
- `ENABLE_SECRETS_BRIDGE=0 openclaw agent --local ...`
  - fails with "No API key found for provider \"groq\" ..."

2) With bridge (no `secrets exec`):
- `ENABLE_SECRETS_BRIDGE=1 openclaw agent --local ...`
  - Groq becomes present and is attempted (auth failures, if any, now correctly attribute to `groq/...`).

## Notes / Caveats
- If Groq returns `401 authentication_error: Invalid bearer token`, the key present in the secrets backend is invalid or stale. Fix via operator action:
  - `ENABLE_SECRETS_BRIDGE=1 openclaw secrets set groq`
  - then `ENABLE_SECRETS_BRIDGE=1 openclaw secrets test groq`
- Ollama OpenAI-compatible generation endpoints on this host were observed hanging while native `POST /api/chat` succeeds; this is outside the System-2 SecretsBridge change but affects local fallback behavior for OpenAI-compatible callers.

## Tests
- `npm test`

## Revert
- `git revert <commit>`

