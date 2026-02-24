'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

function run(name, fn) {
  try {
    fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}: ${error.message}`);
    process.exitCode = 1;
  }
}

run('plugin registers CLI commands: secrets and gateway diag', () => {
  const plugin = require('../scripts/openclaw_secrets_plugin');
  const registered = [];
  plugin.register({
    registerCli: (_fn, opts) => registered.push(opts?.commands || []),
  });
  assert.ok(registered.some((cmds) => cmds.includes('secrets')), registered);
  assert.ok(registered.some((cmds) => cmds.includes('gateway diag')), registered);
});

run('secrets cli status prints enablement header (no secrets)', () => {
  const tmpHome = fs.mkdtempSync(path.join(os.tmpdir(), 'openclaw-secrets-cli-'));
  const script = path.join(__dirname, '..', 'scripts', 'openclaw_secrets_cli.js');
  const env = {
    ...process.env,
    HOME: tmpHome,
    // Force deterministic backend (no keychain access).
    SECRETS_BACKEND: 'file',
    ENABLE_SECRETS_BRIDGE: '0',
  };
  const res = spawnSync(process.execPath, [script, 'status'], {
    env,
    encoding: 'utf8',
  });
  assert.equal(res.status, 0, res.stderr || '');
  assert.match(res.stdout || '', /secrets_bridge_enabled=(true|false)/);
  assert.match(res.stdout || '', /secrets_backend=/);
});

console.log('secrets_cli_plugin tests complete');
