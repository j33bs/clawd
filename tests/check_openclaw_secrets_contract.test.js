'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

function runToolWithHome(homeDir) {
  return spawnSync('bash', ['-lc', 'tools/check_openclaw_secrets_contract.sh'], {
    env: { ...process.env, HOME: homeDir },
    encoding: 'utf8',
  });
}

function writeCfg(homeDir, obj) {
  const dir = path.join(homeDir, '.openclaw');
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'openclaw.json'), JSON.stringify(obj, null, 2) + '\n');
}

test('PASS: valid Groq inline SecretRef + allowlist', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'oc-home-'));
  writeCfg(home, {
    secrets: { providers: { groq: { source: 'env', allowlist: ['GROQ_API_KEY'] } } },
    models: { providers: { groq: { apiKey: { source: 'env', provider: 'groq', id: 'GROQ_API_KEY' } } } },
  });

  const r = runToolWithHome(home);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.match(r.stdout, /PASS:/);
});

test('FAIL: plaintext apiKey rejected', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'oc-home-'));
  writeCfg(home, {
    secrets: { providers: { groq: { source: 'env', allowlist: ['GROQ_API_KEY'] } } },
    models: { providers: { groq: { apiKey: 'PLAINTEXT' } } },
  });

  const r = runToolWithHome(home);
  assert.notEqual(r.status, 0, r.stdout + r.stderr);
  assert.match(r.stdout + r.stderr, /FAIL:/);
});
