#!/usr/bin/env node
'use strict';

const assert = require('node:assert/strict');
const {
  redact,
  createSafeErrorEnvelope,
  adapterPublicErrorFields,
  formatAdapterPublicError
} = require('../workspace/scripts/safe_error_surface');

function run(name, fn) {
  Promise.resolve()
    .then(fn)
    .then(() => console.log(`PASS ${name}`))
    .catch((error) => {
      console.error(`FAIL ${name}: ${error.message}`);
      process.exitCode = 1;
    });
}

run('redact hides bearer/api keys/cookies', () => {
  const input = 'Authorization: Bearer sk-1234567890 cookie: session=abc token=xyz';
  const out = redact(input);
  assert.equal(out.includes('sk-1234567890'), false);
  assert.equal(out.includes('session=abc'), false);
  assert.equal(out.includes('token=xyz'), false);
});

run('safe envelope keeps stable public surface', () => {
  const envelope = createSafeErrorEnvelope({
    publicMessage: 'Request failed. Please retry shortly.',
    errorCode: 'tg-timeout',
    requestId: 'req-123',
    debugSummary: 'timeout'
  });
  const payload = adapterPublicErrorFields(envelope);
  assert.deepEqual(Object.keys(payload).sort(), ['error_code', 'public_message', 'request_id']);
  assert.equal(payload.error_code, 'tg-timeout');
  assert.equal(payload.request_id, 'req-123');
});

run('safe envelope redacts malicious public message text', () => {
  const envelope = createSafeErrorEnvelope({
    publicMessage: 'Authorization: Bearer sk-abc123secret',
    errorCode: 'tg-timeout',
    requestId: 'req-raw'
  });
  assert.equal(envelope.public_message.includes('sk-abc123secret'), false);
  assert.equal(envelope.public_message.includes('<redacted>') || envelope.public_message.includes('<redacted-token>'), true);
});

run('adapter error text excludes internal log hints', () => {
  const envelope = createSafeErrorEnvelope({
    requestId: 'req-222',
    errorCode: 'tg-gateway',
    publicMessage: 'Request failed. Please retry shortly.',
    debugSummary: 'provider_unavailable'
  });
  const text = formatAdapterPublicError(envelope);
  assert.equal(text.includes('Gateway logs contain details'), false);
  assert.equal(text.includes('stack trace'), false);
  assert.equal(text.includes('error_code:'), true);
  assert.equal(text.includes('request_id:'), true);
});
