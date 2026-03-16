const assert = require('node:assert');

const { getProvider } = require('../core/system2/inference/catalog');
const { ProviderAdapter } = require('../core/system2/inference/provider_adapter');
const { redactIfSensitive } = require('../core/system2/inference/config');

function main() {
  const xai = getProvider('xai');
  assert.ok(xai, 'xai provider must exist in catalog');
  assert.strictEqual(xai.base_url.env_override, 'OPENCLAW_XAI_BASE_URL');
  assert.strictEqual(xai.auth.env_var, 'OPENCLAW_XAI_API_KEY');
  assert.deepStrictEqual(xai.auth.alias_env_vars, ['XAI_API_KEY', 'GROK_API_KEY']);
  assert.ok(xai.models.some((m) => m.model_id === 'grok-code-fast-1'), 'xai catalog must include grok-code-fast-1');

  const adapter = new ProviderAdapter(xai, { env: { XAI_API_KEY: 'xai-test-token' } });
  assert.strictEqual(adapter._authToken, 'xai-test-token', 'provider adapter must honor xAI alias env vars');

  assert.strictEqual(redactIfSensitive('XAI_API_KEY', 'xai-secret'), '[REDACTED]');
  console.log('PASS xai provider catalog');
}

if (typeof test === 'function') {
  test('xai provider catalog', () => {
    main();
  });
} else {
  main();
}
