'use strict';

const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const path = require('node:path');

function run(name, fn) {
  try {
    fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}: ${error.message}`);
    process.exitCode = 1;
  }
}

run('provider_diag includes grep-friendly providers_summary section', () => {
  const script = path.join(__dirname, '..', 'scripts', 'system2', 'provider_diag.js');
  const res = spawnSync(process.execPath, [script], {
    env: {
      ...process.env,
      PROVIDER_DIAG_NO_PROBES: '1',
      ENABLE_SECRETS_BRIDGE: '0',
      ENABLE_FREECOMPUTE_CLOUD: '0',
    },
    encoding: 'utf8',
  });

  assert.equal(res.status, 0, res.stderr || '');
  const out = res.stdout || '';

  // Detailed section remains unchanged (dash-prefixed lines).
  assert.match(out, /^providers:\n/m);
  assert.match(out, /^- groq: configured=/m);
  assert.match(out, /^- local_vllm: configured=/m);

  // New stable summary section: provider_id begins at column 0.
  assert.match(out, /^providers_summary:\n/m);
  assert.match(out, /^groq: configured=/m);
  assert.match(out, /^local_vllm: configured=/m);

  // Summary should not include auth_env_keys (keep that in detailed section only).
  const summaryBlock = out.split('providers_summary:\n')[1] || '';
  assert.ok(!/auth_env_keys=/.test(summaryBlock), 'auth_env_keys should not appear in providers_summary');
});

console.log('provider_diag_format tests complete');

