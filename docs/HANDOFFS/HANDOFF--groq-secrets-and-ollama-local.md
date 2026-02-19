# System-2: Groq Free Cloud Preferred + Ollama Local Fallback

## Operating Mode
- Cloud enabled: Groq is preferred when a key is available.
- Local enabled: Ollama (OpenAI-compatible) is used as fallback/escape hatch.
- vLLM is deprecated on this Mac; keep the OpenAI-compatible contract stable by pointing the local lane at Ollama.

## Groq Key (Keychain via Secrets Bridge)
Store (hidden prompt):
```bash
ENABLE_SECRETS_BRIDGE=1 openclaw secrets set groq
```

Verify (no values printed):
```bash
ENABLE_SECRETS_BRIDGE=1 openclaw secrets status | rg -n "^groq:"
ENABLE_SECRETS_BRIDGE=1 openclaw secrets test groq
```

## Enable Cloud Routing
```bash
ENABLE_FREECOMPUTE_CLOUD=1
```

Verify eligibility (names/booleans only):
```bash
ENABLE_SECRETS_BRIDGE=1 ENABLE_FREECOMPUTE_CLOUD=1 node scripts/system2/provider_diag.js | head -n 220
```

## Local Lane (Ollama)
Ollama OpenAI-compatible surface:
- `http://127.0.0.1:11434/v1`

Verify:
```bash
curl -sS --max-time 2 http://127.0.0.1:11434/v1/models | head -c 300; echo
OPENCLAW_VLLM_BASE_URL=http://127.0.0.1:11434/v1 node scripts/vllm_probe.js --json
```

## Notes
- Groq default base URL remains `https://api.groq.com/openai/v1` (the `api.groq.ai` host did not resolve in testing).

