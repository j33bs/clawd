'use strict';

const assert = require('node:assert');

const { createSignedEnvelope, verifyEnvelope } = require('../core/system2/federated_envelope');

function run(name, fn) {
  try {
    fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    console.error(error.message);
    process.exit(1);
  }
}

run('signed envelope verifies with same key', () => {
  const envelope = createSignedEnvelope(
    { input: 'x' },
    { route: 'LOCAL_QWEN' },
    { remaining: 100 },
    [{ id: 'a1' }],
    {
      signingKey: 'test-key'
    }
  );

  const verification = verifyEnvelope(envelope, {
    signingKey: 'test-key'
  });
  assert.strictEqual(verification.ok, true);
});

run('signature mismatch is rejected', () => {
  const envelope = createSignedEnvelope(
    { input: 'x' },
    { route: 'LOCAL_QWEN' },
    { remaining: 100 },
    [{ id: 'a1' }],
    {
      signingKey: 'test-key'
    }
  );
  envelope.payload.input = 'mutated';

  const verification = verifyEnvelope(envelope, {
    signingKey: 'test-key'
  });
  assert.strictEqual(verification.ok, false);
  assert.ok(verification.errors.includes('signature mismatch'));
});
