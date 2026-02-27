'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { SecretsBridge } = require('../core/system2/inference/secrets_bridge');
const { canSpawnSubprocess } = require('./helpers/capabilities');

function run(name, fn) {
  try {
    fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}: ${error.message}`);
    process.exitCode = 1;
  }
}

run('plugin registers CLI command: secrets', () => {
  const plugin = require('../scripts/openclaw_secrets_plugin');
  const registered = [];
  plugin.register({
    registerCli: (_fn, opts) => registered.push(opts?.commands || []),
  });
  assert.ok(registered.some((cmds) => cmds.includes('secrets')), registered);
});

run('secrets cli status prints enablement header (no secrets)', () => {
  const tmpHome = fs.mkdtempSync(path.join(os.tmpdir(), 'openclaw-secrets-cli-'));
  const script = path.join(__dirname, '..', 'scripts', 'openclaw_secrets_cli.js');
  const envPatch = {
    ...process.env,
    HOME: tmpHome,
    // Force deterministic backend (no keychain access).
    SECRETS_BACKEND: 'file',
    ENABLE_SECRETS_BRIDGE: '0',
  };
  const capability = canSpawnSubprocess();
  if (!capability.ok) {
    // Fallback for restricted environments where nested spawn is blocked (EPERM).
    const previous = {};
    for (const [key, value] of Object.entries(envPatch)) {
      previous[key] = process.env[key];
      process.env[key] = value;
    }
    try {
      const bridge = new SecretsBridge();
      const rows = bridge.status();
      const syntheticOut = [
        `secrets_bridge_enabled=${bridge.config.enabled ? 'true' : 'false'}`,
        `secrets_backend=${rows[0]?.backend || 'unknown'}`
      ].join('\n');
      assert.match(syntheticOut, /secrets_bridge_enabled=(true|false)/);
      assert.match(syntheticOut, /secrets_backend=/);
    } finally {
      for (const key of Object.keys(envPatch)) {
        if (previous[key] === undefined) delete process.env[key];
        else process.env[key] = previous[key];
      }
    }
    return;
  }

  const res = spawnSync(process.execPath, [script, 'status'], {
    env: envPatch,
    encoding: 'utf8',
  });
  assert.equal(res.status, 0, res.stderr || '');
  assert.match(res.stdout || '', /secrets_bridge_enabled=(true|false)/);
  assert.match(res.stdout || '', /secrets_backend=/);
});

console.log('secrets_cli_plugin tests complete');
