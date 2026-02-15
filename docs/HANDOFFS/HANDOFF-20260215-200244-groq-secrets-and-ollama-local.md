# System-2 Operating Mode: Groq Free Cloud + Ollama Local Fallback

## Goals
- Use Groq as the primary free cloud fallback when configured.
- Use local inference as a fallback, but avoid vLLM on this Mac (dependency/overhead).
- Keep the OpenAI-compatible contract stable for the local lane: `http://127.0.0.1:11434/v1` (Ollama).

## Local Lane (Ollama)
Evidence (System-2 macOS):
- `curl http://127.0.0.1:11434/api/tags` returns model list.
- `curl http://127.0.0.1:11434/v1/models` returns OpenAI-compatible model list.
- `node scripts/vllm_probe.js --json` succeeds against `OPENCLAW_VLLM_BASE_URL=http://127.0.0.1:11434/v1`.

Notes:
- The System-2 "local_vllm" provider is treated as a generic local OpenAI-compatible endpoint.
- Use `ENABLE_LOCAL_VLLM=0` only if you want to disable the local lane entirely.

## Groq Secrets (Keychain)
Store Groq key via secret-safe CLI (hidden prompt, do not paste key into shell):
```bash
ENABLE_SECRETS_BRIDGE=1 openclaw secrets set groq
```

Verify (no values printed):
```bash
ENABLE_SECRETS_BRIDGE=1 openclaw secrets status | rg -n "^groq:"
ENABLE_SECRETS_BRIDGE=1 openclaw secrets test groq
```

Enable cloud/free routing (either key works):
```bash
ENABLE_FREECOMPUTE_CLOUD=1   # canonical
ENABLE_FREECOMPUTE=1         # alias
```

Then confirm System-2 sees Groq as eligible:
```bash
ENABLE_SECRETS_BRIDGE=1 ENABLE_FREECOMPUTE_CLOUD=1 node scripts/system2/provider_diag.js | rg -n "groq|local_vllm|freecompute_enabled"
```

## Routing Policy
- When cloud is enabled and Groq is configured, external candidates are ranked above local.
- Local remains a fail-closed escape hatch when cloud providers are missing keys/unhealthy/quota-limited.

## Revert
- `git revert <commit>` for the change that updates routing + local defaults.

