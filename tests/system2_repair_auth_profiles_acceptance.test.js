const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert');
const childProcess = require('node:child_process');

function readJson(p) {
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

function main() {
  const repoRoot = path.resolve(__dirname, '..');
  const script = path.join(repoRoot, 'scripts/system2_repair_agent_auth_profiles.sh');

  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'openclaw-system2-auth-repair-'));
  const fixtureHome = path.join(tmp, 'home');
  const fixtureTmp = path.join(tmp, 'tmp');
  fs.mkdirSync(fixtureHome, { recursive: true });
  fs.mkdirSync(fixtureTmp, { recursive: true });

  // Seed a realistic auth store that already has a Gemini OAuth profile.
  // The repair script must prefer OAuth over the env-key fallback profile.
  const seedPath = path.join(fixtureHome, '.clawdbot/agents/main/agent');
  fs.mkdirSync(seedPath, { recursive: true });
  const seedFile = path.join(seedPath, 'auth-profiles.json');
  const oauthId = 'google-gemini-cli:user@example.com';
  const seed = {
    version: 1,
    profiles: {
      [oauthId]: { provider: 'google-gemini-cli', type: 'oauth', access: '', refresh: '', expires: 0 }
    },
    order: {
      'google-gemini-cli': ['google-gemini-cli:default', oauthId]
    },
    lastGood: {},
    usageStats: {}
  };
  fs.writeFileSync(seedFile, JSON.stringify(seed, null, 2) + '\n');

  const env = { ...process.env, HOME: fixtureHome, TMPDIR: fixtureTmp };
  const r = childProcess.spawnSync('sh', [script], { env, encoding: 'utf8' });
  assert.strictEqual(r.status, 0, 'auth profiles repair script must exit 0');

  const runtimeDirs = [
    path.join(fixtureHome, '.clawdbot/agents/main/agent'),
    path.join(fixtureHome, '.clawd/agents/main/agent'),
    path.join(fixtureHome, '.openclaw/agents/main/agent')
  ];

  for (const dir of runtimeDirs) {
    const p = path.join(dir, 'auth-profiles.json');
    assert.ok(fs.existsSync(p), `auth-profiles.json must exist: ${p}`);
    const j = readJson(p);
    assert.ok(j && typeof j === 'object', 'auth store must be JSON object');
    assert.ok(j.profiles && typeof j.profiles === 'object', 'profiles must be an object');
    assert.ok(j.order && typeof j.order === 'object', 'order must be an object map');

    // Required stubs (no secrets stored).
    assert.strictEqual(j.profiles['ollama:default'].type, 'none', 'ollama must be explicit no-auth');
    assert.strictEqual(j.profiles['groq:default'].apiKeyEnv, 'GROQ_API_KEY', 'groq must reference GROQ_API_KEY');
    assert.strictEqual(j.profiles['google-gemini-cli:default'].apiKeyEnv, 'GEMINI_API_KEY', 'gemini must reference GEMINI_API_KEY');
    assert.strictEqual(j.profiles['qwen-portal:default'].type, 'oauth', 'qwen portal must be oauth stub');

    // Provider order must exist for all ladder providers.
    for (const provider of ['google-gemini-cli', 'qwen-portal', 'groq', 'ollama']) {
      assert.ok(Array.isArray(j.order[provider]), `order[${provider}] must be an array`);
      assert.ok(j.order[provider].length > 0, `order[${provider}] must be non-empty`);
    }

    // Gemini must prefer OAuth profile id first if present.
    const geminiOrder = j.order['google-gemini-cli'];
    const hasOauth = Object.keys(j.profiles).some(
      (pid) => j.profiles[pid] && j.profiles[pid].provider === 'google-gemini-cli' && j.profiles[pid].type === 'oauth'
    );
    if (hasOauth) {
      assert.strictEqual(
        geminiOrder[0],
        oauthId,
        'gemini oauth profile must be prioritized ahead of api_key fallback'
      );
    }

    // Local floor must not require keys: ensure ollama:default is first.
    assert.strictEqual(j.order.ollama[0], 'ollama:default', 'ollama:default must be first in order[ollama]');
  }

  console.log('PASS system2 repair auth-profiles acceptance check');
}

main();

