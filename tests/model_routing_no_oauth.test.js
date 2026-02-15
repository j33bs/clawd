const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert');

function readJson(p) {
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

function main() {
  const repoRoot = path.resolve(__dirname, '..');

  const canonicalModelsPath = path.join(repoRoot, 'agents/main/agent/models.json');
  const canonicalTxt = fs.readFileSync(canonicalModelsPath, 'utf8');

  // Fast fail if banned strings creep into the canonical roster.
  for (const needle of ['openai-codex', 'openai_codex']) {
    assert.ok(!canonicalTxt.includes(needle), `canonical models must not contain ${needle}`);
  }
  assert.ok(!canonicalTxt.includes('"apiKey": "ollama"'), 'canonical models must not include ollama sentinel apiKey');

  const canonical = readJson(canonicalModelsPath);
  const providers = canonical.providers || {};
  assert.ok(!Object.prototype.hasOwnProperty.call(providers, 'openai'), 'canonical models must not include provider key "openai"');
  assert.ok(!Object.prototype.hasOwnProperty.call(providers, 'openai-codex'), 'canonical models must not include provider key "openai-codex"');
  assert.ok(!Object.prototype.hasOwnProperty.call(providers, 'openai_codex'), 'canonical models must not include provider key "openai_codex"');
  assert.ok(!Object.prototype.hasOwnProperty.call(providers, 'system2-litellm'), 'canonical models must not include provider key "system2-litellm"');
  assert.ok(!Object.prototype.hasOwnProperty.call(providers, 'anthropic'), 'canonical models must not include provider key "anthropic"');

  for (const required of ['google-gemini-cli', 'qwen-portal', 'groq', 'ollama']) {
    assert.ok(Object.prototype.hasOwnProperty.call(providers, required), `canonical models must include provider key "${required}"`);
  }

  // Local must be no-auth; cloud must be keyable (but no key material committed).
  assert.ok(!Object.prototype.hasOwnProperty.call(providers.ollama || {}, 'apiKey'), 'ollama provider must not require an apiKey in canonical models');
  assert.notStrictEqual((providers.groq || {}).enabled, false, 'groq must not be disabled in canonical models');
  if (Object.prototype.hasOwnProperty.call(providers.groq || {}, 'apiKey')) {
    assert.strictEqual((providers.groq || {}).apiKey, 'GROQ_API_KEY', 'groq.apiKey must refer to env var name (no key material)');
  }

  const policyPath = path.join(repoRoot, 'workspace/policy/llm_policy.json');
  const policy = readJson(policyPath);
  assert.strictEqual(policy.defaults && policy.defaults.preferLocal, true, 'policy.defaults.preferLocal must be true');
  assert.strictEqual(policy.defaults && policy.defaults.allowPaid, false, 'policy.defaults.allowPaid must be false');
  const policyProviders = (policy.providers || {});
  const ollamaPolicy = policyProviders.ollama || {};
  assert.strictEqual(ollamaPolicy.type, 'ollama', 'policy.providers.ollama.type must be "ollama"');
  assert.ok(!('apiKeyEnv' in ollamaPolicy), 'policy.providers.ollama must not require apiKeyEnv');

  const expectedFreeOrder = ['google-gemini-cli', 'qwen-portal', 'groq', 'ollama'];
  assert.deepStrictEqual(policy.routing && policy.routing.free_order, expectedFreeOrder, 'policy.routing.free_order must match expected free ladder');

  // Governance/security/audit must be strictly free with mandatory local floor (ollama last).
  const intents = (policy.routing && policy.routing.intents) || {};
  for (const intentName of ['governance', 'security', 'system2_audit']) {
    const cfg = intents[intentName];
    assert.ok(cfg, `policy.routing.intents.${intentName} must exist`);
    const order = cfg.order || [];
    assert.ok(Array.isArray(order), `policy.routing.intents.${intentName}.order must be an array`);
    assert.deepStrictEqual(order, expectedFreeOrder, `policy.routing.intents.${intentName}.order must match expected free ladder`);
    const joined = order.join(',');
    for (const banned of ['openai', 'openai_auth', 'openai_api', 'openai-codex', 'openai_codex', 'claude_auth']) {
      assert.ok(!joined.includes(banned), `policy.routing.intents.${intentName}.order must not reference ${banned}`);
    }
    assert.strictEqual(cfg.allowPaid, false, `policy.routing.intents.${intentName}.allowPaid must be false`);
  }

  console.log('PASS model routing no oauth/codex regression gate');
}

main();
