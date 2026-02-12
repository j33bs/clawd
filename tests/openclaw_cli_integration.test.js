#!/usr/bin/env node
'use strict';

const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const { SecretsBridge } = require('../core/system2/inference/secrets_bridge');

function test(name, fn) {
  try {
    fn();
    console.log('PASS ' + name);
  } catch (error) {
    console.error('FAIL ' + name + ': ' + error.message);
    process.exitCode = 1;
  }
}

function runOpenclaw(args, extraEnv = {}) {
  const cliPath = path.resolve(__dirname, '..', 'scripts', 'openclaw_cli.js');
  return spawnSync(process.execPath, [cliPath, ...args], {
    encoding: 'utf8',
    env: {
      ...process.env,
      ...extraEnv
    }
  });
}

test('openclaw secrets --help exits 0 and prints help text', function () {
  const run = runOpenclaw(['secrets', '--help']);
  assert.strictEqual(run.status, 0);
  assert.match(run.stdout, /secrets\s+Manage API keys for providers \(store, test, list\)/);
  assert.match(run.stdout, /set\s+Store a provider API key/);
  assert.match(run.stdout, /status\s+Show which provider keys are configured/);
});

test('openclaw --help includes secrets subcommand summary', function () {
  const run = runOpenclaw(['--help']);
  assert.strictEqual(run.status, 0);
  assert.match(run.stdout, /secrets\s+Manage API keys for providers \(store, test, list\)/);
});

test('openclaw secrets status exits 0 and does not print secret values', function () {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'clawd-secrets-home-'));
  const run = runOpenclaw(['secrets', 'status'], {
    ENABLE_SECRETS_BRIDGE: '1',
    SECRETS_BACKEND: 'file',
    SECRETS_FILE_PASSPHRASE: 'test-passphrase',
    HOME: home,
    USERPROFILE: home
  });
  assert.strictEqual(run.status, 0);
  assert.match(run.stdout, /^groq: /m);
  assert.doesNotMatch(run.stdout, /mock_secret_/);
  assert.doesNotMatch(run.stdout, /test-passphrase/);
});

test('openclaw secrets command exits cleanly when bridge disabled', function () {
  const run = runOpenclaw(['secrets', 'status'], {
    ENABLE_SECRETS_BRIDGE: '0'
  });
  assert.strictEqual(run.status, 0);
  assert.match(run.stdout, /Secrets Bridge is disabled \(ENABLE_SECRETS_BRIDGE=0\)/);
});

test('openclaw secrets test exits cleanly when bridge disabled', function () {
  const run = runOpenclaw(['secrets', 'test', 'groq'], {
    ENABLE_SECRETS_BRIDGE: '0'
  });
  assert.strictEqual(run.status, 0);
  assert.match(run.stdout, /Secrets Bridge is disabled \(ENABLE_SECRETS_BRIDGE=0\)/);
});

test('openclaw dashboard passthrough applies secrets bridge injection when enabled', function () {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'clawd-secrets-dashboard-home-'));
  const captureDir = fs.mkdtempSync(path.join(os.tmpdir(), 'clawd-openclaw-capture-'));
  const capturePath = path.join(captureDir, 'capture.json');
  const passthroughPath = path.join(captureDir, 'mock-openclaw');
  const secretValue = 'mock_secret_bridge_injection_1234';
  const secretsFilePath = path.join(home, '.openclaw', 'secrets.enc');

  const bootstrapEnv = {
    ENABLE_SECRETS_BRIDGE: '1',
    SECRETS_BACKEND: 'file',
    SECRETS_FILE_PASSPHRASE: 'test-passphrase',
    HOME: home,
    USERPROFILE: home
  };

  const bridge = new SecretsBridge({ env: bootstrapEnv, secretsFilePath });
  bridge.setSecret('groq', secretValue, { passphrase: 'test-passphrase' });

  const mockScript = [
    '#!/usr/bin/env node',
    "'use strict';",
    "const fs = require('node:fs');",
    'const payload = {',
    '  argv: process.argv.slice(2),',
    "  hasGroqKey: !!process.env.OPENCLAW_GROQ_API_KEY",
    '};',
    "fs.writeFileSync(process.env.OPENCLAW_TEST_CAPTURE_PATH, JSON.stringify(payload), 'utf8');"
  ].join('\n');
  fs.writeFileSync(passthroughPath, mockScript + '\n', { mode: 0o755 });

  const run = runOpenclaw(['dashboard', '--json'], {
    ...bootstrapEnv,
    OPENCLAW_CLI_PASSTHROUGH_BIN: passthroughPath,
    OPENCLAW_TEST_CAPTURE_PATH: capturePath
  });

  assert.strictEqual(run.status, 0);
  assert.ok(fs.existsSync(capturePath), 'mock passthrough output should exist');
  const payload = JSON.parse(fs.readFileSync(capturePath, 'utf8'));
  assert.deepStrictEqual(payload.argv, ['dashboard', '--json']);
  assert.strictEqual(payload.hasGroqKey, true);
  assert.doesNotMatch(run.stdout, new RegExp(secretValue));
  assert.doesNotMatch(run.stderr, new RegExp(secretValue));
});
