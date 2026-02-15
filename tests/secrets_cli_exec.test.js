#!/usr/bin/env node
'use strict';

const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const path = require('node:path');

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
    env: {
      ...process.env,
      ENABLE_SECRETS_BRIDGE: '1',
      // Operator override path: injectRuntimeEnv should propagate to GROQ_API_KEY alias.
      OPENCLAW_GROQ_API_KEY: 'x'
    }
  });

  assert.equal(res.status, 0, res.stderr || 'non-zero exit');
  const out = String(res.stdout || '');
  assert.ok(out.includes('secrets_bridge_injected_env_keys='), 'expected injected env key summary');
  assert.ok(out.includes('GROQ_API_KEY_present=true'));
  assert.ok(out.includes('OPENCLAW_GROQ_API_KEY_present=true'));
  assert.ok(!out.includes('OPENCLAW_GROQ_API_KEY=x'), 'secret value leaked');
});

