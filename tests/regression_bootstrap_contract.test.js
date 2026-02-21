#!/usr/bin/env node
'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

function test(name, fn) {
  try {
    fn();
    console.log('PASS ' + name);
  } catch (error) {
    console.error('FAIL ' + name + ': ' + error.message);
    process.exitCode = 1;
  }
}

test('regression.sh bootstraps ephemeral config when openclaw.json is absent', function () {
  const repoRoot = path.resolve(__dirname, '..');
  const res = spawnSync('bash', ['workspace/scripts/regression.sh'], {
    cwd: repoRoot,
    encoding: 'utf8',
    env: {
      ...process.env,
      OPENCLAW_CONFIG_PATH: ''
    }
  });

  const output = String(res.stdout || '') + String(res.stderr || '');
  assert.equal(res.status, 0, output);
  assert.ok(output.includes('[regression] Using ephemeral OPENCLAW_CONFIG_PATH='), 'expected ephemeral config bootstrap log');
  assert.ok(!output.includes('openclaw config not found for provider gating check'), 'missing-config hard fail must not occur');
});
