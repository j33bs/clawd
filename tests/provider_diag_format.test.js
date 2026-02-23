'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');

async function run(name, fn) {
  try {
    await fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}: ${error.message}`);
    process.exitCode = 1;
  }
}

async function main() {
  await run('provider_diag includes grep-friendly providers_summary section', async () => {
    const script = path.join(__dirname, '..', 'scripts', 'system2', 'provider_diag.js');
    const { generateDiagnostics } = require(script);
    const out = await generateDiagnostics({
      ...process.env,
      PROVIDER_DIAG_NO_PROBES: '1',
      ENABLE_SECRETS_BRIDGE: '0',
      ENABLE_FREECOMPUTE_CLOUD: '0',
    });

    // New stable canary/coder markers.
    assert.match(out, /^coder_status=/m);
    assert.match(out, /^coder_degraded_reason=/m);
    assert.match(out, /^replay_log_writable=/m);
    assert.match(out, /^pairing_canary_status=/m);
    assert.match(out, /^event_envelope_schema=openclaw\.event_envelope\.v1$/m);
    assert.match(out, /^actionable_next_steps:\n/m);
    assert.match(out, /^canary_recommendations:\n/m);

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
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : String(error));
  process.exitCode = 1;
});
