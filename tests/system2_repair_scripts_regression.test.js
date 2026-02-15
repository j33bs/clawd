const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert');

function main() {
  const repoRoot = path.resolve(__dirname, '..');

  // Ensure the runtime repair scripts stay narrowly scoped:
  // - remove OpenAI/Codex provider lanes and model IDs
  // - do NOT scrub "/openai/" substrings in URLs (Groq uses an OpenAI-compatible base URL)
  const modelsRepairPath = path.join(repoRoot, 'scripts/system2_repair_agent_models.sh');
  const modelsRepairTxt = fs.readFileSync(modelsRepairPath, 'utf8');

  assert.ok(modelsRepairTxt.includes('BANNED_PROVIDER_KEYS'), 'models repair script must define BANNED_PROVIDER_KEYS');
  assert.ok(modelsRepairTxt.includes('system2-litellm'), 'models repair script must remove system2-litellm lane');
  assert.ok(modelsRepairTxt.includes('openai-codex'), 'models repair script must remove openai-codex lanes');
  // Prefix-based scrub: allow refactors (e.g., s.startswith(m) vs explicit literals), but require prefix semantics.
  assert.ok(modelsRepairTxt.includes('openai/'), 'models repair must reference openai/ model-id prefix');
  assert.ok(modelsRepairTxt.includes('openai-codex/'), 'models repair must reference openai-codex/ model-id prefix');
  assert.ok(/startswith\s*\(/.test(modelsRepairTxt), 'models repair must use startswith(...) prefix checks (not substring scans)');
  assert.ok(!/m\s+in\s+s\s+for\s+m\s+in\s+MARKERS/.test(modelsRepairTxt), 'models repair must not treat MARKERS as generic substrings');
  assert.ok(!modelsRepairTxt.includes('OLLAMA_API_KEY'), 'models repair script must not inject or depend on OLLAMA_API_KEY');

  const authRepairPath = path.join(repoRoot, 'scripts/system2_repair_agent_auth_profiles.sh');
  const authRepairTxt = fs.readFileSync(authRepairPath, 'utf8');
  assert.ok(authRepairTxt.includes('ollama:default'), 'auth profiles repair must ensure ollama:default exists');
  assert.ok(authRepairTxt.includes('"type": "none"'), 'auth profiles repair must write ollama profile as type none (no-auth)');
  assert.ok(authRepairTxt.includes('GEMINI_API_KEY'), 'auth profiles repair must reference GEMINI_API_KEY (no value)');
  assert.ok(authRepairTxt.includes('GROQ_API_KEY'), 'auth profiles repair must reference GROQ_API_KEY (no value)');

  console.log('PASS system2 repair scripts regression gate');
}

main();
