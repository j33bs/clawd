#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUT="$(mktemp "${TMPDIR:-/tmp}/xai-failover-sim.XXXXXX.log")"
trap 'rm -f "$OUT"' EXIT

node >"$OUT" <<'NODE'
'use strict';

const path = require('node:path');

const routerPath = path.resolve(process.cwd(), 'core/system2/inference/router.js');
require.cache[routerPath] = {
  id: routerPath,
  filename: routerPath,
  loaded: true,
  exports: {
    routeRequest: () => ({
      candidates: [{ provider_id: 'xai', model_id: 'xai/grok-4-1-fast' }]
    }),
    explainRouting: () => ({})
  }
};

const { ProviderRegistry } = require('./core/system2/inference/provider_registry');
const { ProviderAdapter } = require('./core/system2/inference/provider_adapter');

const env = {
  ...process.env,
  ENABLE_FREECOMPUTE_CLOUD: '1',
  ENABLE_LOCAL_VLLM: '0',
  OPENCLAW_INTEGRITY_GUARD: '0',
  OPENCLAW_XAI_SIMULATE_BILLING_EXHAUST: '1'
};

const events = [];
const registry = new ProviderRegistry({
  env,
  emitEvent: (eventType, payload) => events.push({ eventType, payload })
});

registry._adapters.clear();
registry._health.clear();
registry._circuitBreakers.clear();

const xaiCatalogEntry = {
  provider_id: 'xai',
  kind: 'external',
  protocol: 'openai_compatible',
  base_url: {
    default: 'http://127.0.0.1:9/v1',
    env_override: 'OPENCLAW_XAI_BASE_URL'
  },
  auth: {
    type: 'bearer_optional',
    env_var: 'OPENCLAW_XAI_API_KEY'
  },
  models: [{ model_id: 'xai/grok-4-1-fast' }],
  healthcheck: {
    type: 'openai_compatible',
    endpoints: { models: '/models', chat: '/chat/completions' },
    timeouts_ms: { connect: 100, read: 100 }
  }
};

const xaiAdapter = new ProviderAdapter(xaiCatalogEntry, { env, emitEvent: () => {} });
const minimaxAdapter = {
  async call({ metadata }) {
    return {
      text: 'FALLBACK_OK',
      model: (metadata && metadata.model) || 'MiniMax-M2.1',
      raw: { ok: true },
      usage: {
        inputTokens: 1,
        outputTokens: 1,
        totalTokens: 2,
        estimatedCostUsd: 0
      }
    };
  }
};

registry._adapters.set('xai', xaiAdapter);
registry._adapters.set('minimax-portal', minimaxAdapter);
registry._circuitBreakers.set('xai', {
  state: 'CLOSED',
  failures: 0,
  timeoutFailures: 0,
  openedAt: 0
});
registry._circuitBreakers.set('minimax-portal', {
  state: 'CLOSED',
  failures: 0,
  timeoutFailures: 0,
  openedAt: 0
});

(async () => {
  const result = await registry.dispatch({
    taskClass: 'fast_chat',
    messages: [{ role: 'user', content: 'ping' }],
    metadata: { model: 'xai/grok-4-1-fast' }
  });

  if (!result) {
    throw new Error('dispatch_result_missing');
  }
  if (result.provider_id !== 'minimax-portal') {
    throw new Error(`unexpected_provider:${result.provider_id}`);
  }
  if (result.model_id !== 'MiniMax-M2.1') {
    throw new Error(`unexpected_model:${result.model_id}`);
  }

  const failoverEvent = events.find((evt) => evt.eventType === 'freecompute_model_failover');
  if (!failoverEvent) {
    throw new Error('failover_event_missing');
  }

  console.log(`FINAL_PROVIDER=${result.provider_id}`);
  console.log(`FINAL_MODEL=${result.model_id}`);
  console.log(`EVENT_REASON=${String(failoverEvent.payload.reason || '')}`);
})().catch((error) => {
  console.error(`SIM_FAIL=${error.message}`);
  process.exit(1);
});
NODE

cat "$OUT"

grep -q "MODEL_FAILOVER provider=xai reason=billing_or_quota primary=xai/grok-4-1-fast fallback=minimax-portal/MiniMax-M2.1" "$OUT"
grep -q "FINAL_PROVIDER=minimax-portal" "$OUT"
grep -q "FINAL_MODEL=MiniMax-M2.1" "$OUT"

echo "xai_failover_simulated:PASS"
