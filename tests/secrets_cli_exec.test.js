#!/usr/bin/env node
'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const { spawnSync } = require('node:child_process');
const path = require('node:path');
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

test('secrets cli exec injects alias env keys without printing values', function () {
  const cli = path.join(__dirname, '..', 'scripts', 'openclaw_secrets_cli.js');
  const tempHome = fs.mkdtempSync(path.join(os.tmpdir(), 'openclaw-secrets-cli-'));
  const envPatch = {
    ENABLE_SECRETS_BRIDGE: '1',
    NODE_ENV: 'test',
    // Keep test deterministic: do not rely on OS keychain/secret-service state.
    SECRETS_BACKEND: 'file',
    SECRETS_FILE_PASSPHRASE: 'test-passphrase',
    HOME: tempHome,
    USERPROFILE: tempHome,
    // Operator override path: injectRuntimeEnv should propagate to GROQ_API_KEY alias.
    OPENCLAW_GROQ_API_KEY: 'x',
    // Set all providers so injectRuntimeEnv does not call external secret stores.
    OPENCLAW_GEMINI_API_KEY: 'x',
    OPENCLAW_OPENROUTER_API_KEY: 'x',
    OPENCLAW_MINIMAX_PORTAL_API_KEY: 'x',
    OPENCLAW_QWEN_API_KEY: 'x',
    OPENCLAW_VLLM_API_KEY: 'x'
  };
  const probe = spawnSync(process.execPath, ['-e', 'process.exit(0)'], { encoding: 'utf8' });
  if (probe.error) {
    // Fallback for restricted environments where nested spawn is blocked (EPERM).
    const previous = {};
    for (const [key, value] of Object.entries(envPatch)) {
      previous[key] = process.env[key];
      process.env[key] = value;
    }
    try {
      const bridge = new SecretsBridge();
      const childEnv = { ...process.env };
      const injection = bridge.injectRuntimeEnv(childEnv);
      const injectedKeys = new Set((injection.injected || []).map((entry) => entry.envVar));
      assert.ok(injectedKeys.has('GROQ_API_KEY'));
      assert.equal(childEnv.GROQ_API_KEY, 'x');
      assert.equal(childEnv.OPENCLAW_GROQ_API_KEY, 'x');
    } finally {
      for (const key of Object.keys(envPatch)) {
        if (previous[key] === undefined) delete process.env[key];
        else process.env[key] = previous[key];
      }
    }
    return;
  }

  const res = spawnSync(process.execPath, [
    cli,
    'exec',
    '--',
    process.execPath,
    '-e',
    // Print presence booleans only; never print secret values.
    'console.log("GROQ_API_KEY_present=" + ("GROQ_API_KEY" in process.env)); console.log("OPENCLAW_GROQ_API_KEY_present=" + ("OPENCLAW_GROQ_API_KEY" in process.env));'
  ], {
    encoding: 'utf8',
    env: { ...process.env, ...envPatch }
  });

  assert.equal(res.status, 0, res.stderr || 'non-zero exit');
  const out = String(res.stdout || '');
  assert.ok(out.includes('secrets_bridge_injected_env_keys='), 'expected injected env key summary');
  assert.ok(out.includes('GROQ_API_KEY_present=true'));
  assert.ok(out.includes('OPENCLAW_GROQ_API_KEY_present=true'));
  assert.ok(!out.includes('OPENCLAW_GROQ_API_KEY=x'), 'secret value leaked');
});
