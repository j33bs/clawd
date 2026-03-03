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
  await run('provider_diag maps coder journal marker to explicit degraded reason', async () => {
    const script = path.join(__dirname, '..', 'scripts', 'system2', 'provider_diag.js');
    const { generateDiagnostics } = require(script);
    const out = await generateDiagnostics({
      ...process.env,
      PROVIDER_DIAG_NO_PROBES: '1',
      ENABLE_SECRETS_BRIDGE: '0',
      ENABLE_FREECOMPUTE_CLOUD: '0',
      PROVIDER_DIAG_JOURNAL_TEXT: 'VLLM_CODER_START_BLOCKED reason=VRAM_LOW free_mb=1466 min_free_mb=7000'
    });

    assert.match(out, /^coder_status=DEGRADED$/m);
    assert.match(out, /^coder_degraded_reason=VRAM_LOW$/m);
    assert.match(out, /^coder_degraded_note=journal_marker$/m);
  });

  console.log('provider_diag_coder_reason tests complete');
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : String(error));
  process.exitCode = 1;
});
