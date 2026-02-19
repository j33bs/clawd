# System-1 Routing Policy

## Policy

System-1 uses `LOCAL_FIRST` routing: prefer `local_vllm` for low-latency local compute, then fall back to `minimax-portal` when local is unavailable or disabled.

Fail-closed rules:
- If `ENABLE_LOCAL_VLLM=0`, local routing is skipped.
- If `OPENCLAW_MINIMAX_PORTAL_API_KEY` is unset, `minimax-portal` is not eligible.
- If both are unavailable, no external provider is selected by FreeComputeCloud.

## Required Environment Variables

- `ENABLE_LOCAL_VLLM`
- `OPENCLAW_VLLM_BASE_URL`
- `FREECOMPUTE_PROVIDER_ALLOWLIST`
- `OPENCLAW_MINIMAX_PORTAL_API_KEY`

Recommended profile file: `env.d/system1-routing.env`.

## Setup Steps (Ubuntu)

1. Load routing profile.

```bash
cd /home/jeebs/src/clawd
set -a
source env.d/system1-routing.env
set +a
```

2. Provide MiniMax key without committing secrets.

```bash
# Option A: shell only (session scoped)
export OPENCLAW_MINIMAX_PORTAL_API_KEY='...'

# Option B: repo secret bridge CLI (interactive, preferred)
npm run secrets -- set minimax-portal
npm run --silent secrets -- status | rg minimax-portal
```

3. Start local vLLM (example command used by repo helper).

```bash
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-Coder-7B-Instruct \
  --port 18888 \
  --gpu-memory-utilization 0.90 \
  --trust-remote-code
```

4. Validate vLLM endpoint and gateway.

```bash
curl -fsS "${OPENCLAW_VLLM_BASE_URL}/models" | head
openclaw gateway status
openclaw gateway health
```

5. Validate routing decision (local first, MiniMax fallback).

```bash
node - <<'NODE'
const { ProviderRegistry } = require('./core/system2/inference');
const reg = new ProviderRegistry({ env: process.env });
console.log('adapters=', reg.snapshot().adapters.map(a => a.provider_id));
console.log(reg.explain({ taskClass: 'code', contextLength: 1000, latencyTarget: 'medium' }));
reg.dispose();
NODE
```

6. Run System-2 experiment and snapshot evidence.

```bash
npm run system2:experiment -- --out .tmp/system1_local_first --fail-on log_signature_counts.auth_error --no-prompt
npm run system2:snapshot -- --out .tmp/system1_snapshot
```

## Code Contract References

- Catalog entries and provider IDs: `core/system2/inference/catalog.js`
- Adapter eligibility (auth + allowlist + local gate): `core/system2/inference/provider_registry.js`
- Routing explanation and scoring: `core/system2/inference/router.js`
- vLLM provider probe/start helper: `core/system2/inference/vllm_provider.js`
- MiniMax secrets mapping: `core/system2/inference/secrets_bridge.js`
