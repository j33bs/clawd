const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert');
const childProcess = require('node:child_process');

function readJson(p) {
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

function providersSet(j) {
  const providers = (j && j.providers) || {};
  return new Set(Object.keys(providers));
}

function assertSetEq(actualSet, expectedArray, label) {
  const actual = Array.from(actualSet).sort();
  const expected = Array.from(new Set(expectedArray)).sort();
  assert.deepStrictEqual(actual, expected, `${label}: providers set mismatch`);
}

function assertNoBannedModelIdPrefixes(jsonObj, label) {
  const banned = ['openai/', 'openai-codex/'];
  let found = 0;
  function walk(x) {
    if (!x) return;
    if (typeof x === 'string') {
      for (const p of banned) {
        if (x.startsWith(p)) found += 1;
      }
      return;
    }
    if (Array.isArray(x)) {
      for (const v of x) walk(v);
      return;
    }
    if (typeof x === 'object') {
      for (const k of Object.keys(x)) {
        for (const p of banned) {
          if (k.startsWith(p)) found += 1;
        }
        walk(x[k]);
      }
    }
  }
  walk(jsonObj);
  assert.strictEqual(found, 0, `${label}: must not contain model IDs starting with openai/ or openai-codex/`);
}

function main() {
  const repoRoot = path.resolve(__dirname, '..');
  const srcScript = path.join(repoRoot, 'scripts/system2_repair_agent_models.sh');
  const srcAuthScript = path.join(repoRoot, 'scripts/system2_repair_agent_auth_profiles.sh');

  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'openclaw-system2-repair-accept-'));
  const fixtureRepo = path.join(tmp, 'repo');
  const fixtureHome = path.join(tmp, 'home');
  const fixtureTmp = path.join(tmp, 'tmp');
  fs.mkdirSync(fixtureRepo, { recursive: true });
  fs.mkdirSync(fixtureHome, { recursive: true });
  fs.mkdirSync(fixtureTmp, { recursive: true });

  // Build a minimal fixture repo layout so the repair script uses fixture canonical models.
  fs.mkdirSync(path.join(fixtureRepo, 'scripts'), { recursive: true });
  fs.mkdirSync(path.join(fixtureRepo, 'agents/main/agent'), { recursive: true });

  const fixtureScript = path.join(fixtureRepo, 'scripts/system2_repair_agent_models.sh');
  const fixtureAuthScript = path.join(fixtureRepo, 'scripts/system2_repair_agent_auth_profiles.sh');
  fs.copyFileSync(srcScript, fixtureScript);
  fs.copyFileSync(srcAuthScript, fixtureAuthScript);
  fs.chmodSync(fixtureScript, 0o755);
  fs.chmodSync(fixtureAuthScript, 0o755);

  // Canonical fixture models includes banned lanes and banned model ids to prove the scrub is effective,
  // and includes Groq baseUrl containing "/openai/v1" which must remain untouched.
  const canonicalFixture = {
    providers: {
      'google-gemini-cli': { api: 'google-gemini-cli', models: [{ id: 'gemini-3-pro-preview' }] },
      'qwen-portal': { baseUrl: 'https://portal.qwen.ai/v1', api: 'openai-completions', apiKey: 'qwen-oauth', models: [{ id: 'coder-model' }] },
      groq: { baseUrl: 'https://api.groq.com/openai/v1', api: 'openai-completions', apiKey: 'GROQ_API_KEY', models: [{ id: 'llama-3.3-70b-versatile' }] },
      ollama: { baseUrl: 'http://localhost:11434/v1', api: 'openai-completions', models: [{ id: 'qwen2.5-coder:7b' }], enabled: 'auto' },
      // Banned provider lanes (must be removed).
      openai: { baseUrl: 'https://api.openai.com/v1', api: 'openai-completions', models: [{ id: 'openai/gpt-4o-mini' }] },
      'system2-litellm': { api: 'openai-completions', models: [{ id: 'system2-litellm/local-coordinator' }] },
    },
    // Also include banned model ids in a flat list to prove recursive scrub.
    models: ['openai/gpt-4o-mini', 'openai-codex/gpt-5.3-codex'],
  };
  const canonicalPath = path.join(fixtureRepo, 'agents/main/agent/models.json');
  fs.writeFileSync(canonicalPath, JSON.stringify(canonicalFixture, null, 2) + '\n');

  // Run the repair script with a fixture HOME so it writes runtime files under the fixture.
  const env = { ...process.env, HOME: fixtureHome, TMPDIR: fixtureTmp };
  const r = childProcess.spawnSync('sh', [fixtureScript], { env, encoding: 'utf8' });
  assert.strictEqual(r.status, 0, 'repair script must exit 0');

  const runtimeModelsPath = path.join(fixtureHome, '.clawdbot/agents/main/agent/models.json');
  assert.ok(fs.existsSync(runtimeModelsPath), 'runtime models.json must be written');
  const runtime = readJson(runtimeModelsPath);

  // Acceptance: providers SET == expected (order irrelevant).
  assertSetEq(
    providersSet(runtime),
    ['google-gemini-cli', 'qwen-portal', 'groq', 'ollama'],
    'runtime models after repair'
  );

  // Groq baseUrl must keep "/openai/v1" (no substring scrub).
  const groq = (runtime.providers || {}).groq || {};
  assert.ok(
    typeof groq.baseUrl === 'string' && groq.baseUrl.includes('/openai/v1'),
    'groq.baseUrl must retain /openai/v1'
  );

  // Must not contain banned provider lanes or model-id prefixes.
  assert.ok(!(runtime.providers || {})['system2-litellm'], 'system2-litellm must be absent from runtime providers');
  assert.ok(!(runtime.providers || {}).openai, 'openai provider must be absent from runtime providers');
  assertNoBannedModelIdPrefixes(runtime, 'runtime models after repair');

  console.log('PASS system2 repair models acceptance check');
}

main();

