'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');

const mod = require(path.join(__dirname, '..', 'scripts', 'system2', 'telegram_reliability.js'));

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
  await run('large payloads are deferred', async () => {
    const payload = { message: { text: 'x'.repeat(4000) } };
    const d = mod.shouldDefer(payload, { threshold: 2000 });
    assert.equal(d.defer, true);
    assert.equal(d.reason, 'payload_large');
  });

  await run('media payloads are deferred', async () => {
    const payload = { message: { text: 'short', document: { file_id: 'abc' } } };
    const d = mod.shouldDefer(payload, { threshold: 2000 });
    assert.equal(d.defer, true);
    assert.equal(d.reason, 'media_payload');
  });

  await run('retry helper retries transient failure once', async () => {
    let attempts = 0;
    const out = await mod.withRetry(
      async () => {
        attempts += 1;
        if (attempts < 2) throw new Error('transient');
        return 'ok';
      },
      { retries: 2, baseDelayMs: 1 }
    );
    assert.equal(out, 'ok');
    assert.equal(attempts, 2);
  });

  console.log('telegram_defer tests complete');
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : String(error));
  process.exitCode = 1;
});
