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

  const canonical = readJson(canonicalModelsPath);
  const providers = canonical.providers || {};
  assert.ok(!Object.prototype.hasOwnProperty.call(providers, 'openai'), 'canonical models must not include provider key "openai"');
  assert.ok(!Object.prototype.hasOwnProperty.call(providers, 'openai-codex'), 'canonical models must not include provider key "openai-codex"');
  assert.ok(!Object.prototype.hasOwnProperty.call(providers, 'openai_codex'), 'canonical models must not include provider key "openai_codex"');

  const policyPath = path.join(repoRoot, 'workspace/policy/llm_policy.json');
  const policy = readJson(policyPath);
  assert.strictEqual(policy.defaults && policy.defaults.preferLocal, true, 'policy.defaults.preferLocal must be true');
  assert.strictEqual(policy.defaults && policy.defaults.allowPaid, false, 'policy.defaults.allowPaid must be false');

  // Governance/security/audit must be local-floor without OAuth/OpenAI lanes.
  const intents = (policy.routing && policy.routing.intents) || {};
  for (const intentName of ['governance', 'security', 'system2_audit']) {
    const cfg = intents[intentName];
    assert.ok(cfg, `policy.routing.intents.${intentName} must exist`);
    const order = cfg.order || [];
    assert.ok(Array.isArray(order), `policy.routing.intents.${intentName}.order must be an array`);
    const joined = order.join(',');
    for (const banned of ['openai', 'openai_auth', 'openai_api', 'openai-codex', 'openai_codex', 'claude_auth']) {
      assert.ok(!joined.includes(banned), `policy.routing.intents.${intentName}.order must not reference ${banned}`);
    }
    assert.strictEqual(cfg.allowPaid, false, `policy.routing.intents.${intentName}.allowPaid must be false`);
  }

  console.log('PASS model routing no oauth/codex regression gate');
}

main();

