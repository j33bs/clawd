'use strict';

const assert = require('node:assert/strict');
const os = require('node:os');
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

function baseEnv() {
  return {
    ...process.env,
    PROVIDER_DIAG_NO_PROBES: '1',
    ENABLE_SECRETS_BRIDGE: '0',
    ENABLE_FREECOMPUTE_CLOUD: '0',
    OPENCLAW_VLLM_CODER_LOG_PATH: path.join(os.tmpdir(), `provider_diag_missing_${Date.now()}_${Math.random()}.log`)
  };
}

async function main() {
  const script = path.join(__dirname, '..', 'scripts', 'system2', 'provider_diag.js');
  const { generateDiagnostics } = require(script);

  await run('journal unavailable maps to UNAVAILABLE and never UNKNOWN', async () => {
    const out = await generateDiagnostics({
      ...baseEnv(),
      PROVIDER_DIAG_JOURNAL_FORCE_UNAVAILABLE: 'EACCES'
    });
    assert.match(out, /^coder_status=DOWN$/m);
    assert.match(out, /^coder_degraded_reason=UNAVAILABLE$/m);
    assert.match(out, /^coder_degraded_note=journal_unavailable$/m);
    assert.doesNotMatch(out, /^coder_degraded_reason=UNKNOWN$/m);
  });

  await run('journal marker maps to DEGRADED reason from marker', async () => {
    const out = await generateDiagnostics({
      ...baseEnv(),
      PROVIDER_DIAG_JOURNAL_TEXT: 'VLLM_CODER_START_BLOCKED reason=VRAM_LOW free_mb=1466 min_free_mb=7000'
    });
    assert.match(out, /^coder_status=DEGRADED$/m);
    assert.match(out, /^coder_degraded_reason=VRAM_LOW$/m);
    assert.match(out, /^coder_degraded_note=journal_marker$/m);
    assert.doesNotMatch(out, /^coder_degraded_reason=UNKNOWN$/m);
  });

  await run('journal with no marker maps to NO_BLOCK_MARKER and DOWN', async () => {
    const out = await generateDiagnostics({
      ...baseEnv(),
      PROVIDER_DIAG_JOURNAL_TEXT: 'coder boot attempt without block marker'
    });
    assert.match(out, /^coder_status=DOWN$/m);
    assert.match(out, /^coder_degraded_reason=NO_BLOCK_MARKER$/m);
    assert.match(out, /^coder_degraded_note=journal_no_marker$/m);
    assert.doesNotMatch(out, /^coder_degraded_reason=UNKNOWN$/m);
  });

  console.log('provider_diag_never_unknown tests complete');
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : String(error));
  process.exitCode = 1;
});
