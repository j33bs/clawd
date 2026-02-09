'use strict';

const assert = require('node:assert');

const { redactValue } = require('../sys/audit/redaction');
const { createAuditEvent } = require('../sys/audit/schema');
const { appendAuditEvent } = require('../sys/audit/logger');

function pass(name) {
  console.log(`PASS ${name}`);
}

function testKeyRedaction() {
  const redacted = redactValue({ token: 'abc123', payload: { message: 'hello', size: 4 } });
  assert.strictEqual(redacted.token, '[REDACTED]');
  assert.strictEqual(redacted.payload.message, '[REDACTED]');
  assert.strictEqual(redacted.payload.size, 4);
  pass('sensitive keys are redacted');
}

function testValuePatternRedaction() {
  const redacted = redactValue({ note: 'Bearer abcdefghijklmnop', safe: 'ok' });
  assert.strictEqual(redacted.note, '[REDACTED]');
  assert.strictEqual(redacted.safe, 'ok');
  pass('sensitive value patterns are redacted');
}

function testLoggerNeverWritesSecrets() {
  const event = createAuditEvent({
    ts: 1739059200000,
    eventType: 'audit.operator.notice',
    runId: 'run-redact',
    git: { branch: 'main', headSha: 'abc', dirty: false },
    host: { platform: 'darwin', nodeVersion: process.version },
    config: { sysConfigHash: 'x', openclawConfigHash: 'y' },
    payload: { token: 'sk-secret-token', message: 'raw prompt data' }
  });

  const result = appendAuditEvent(event, { enabled: false });
  assert.strictEqual(result.written, false);
  pass('logger obeys opt-in gate');
}

function main() {
  testKeyRedaction();
  testValuePatternRedaction();
  testLoggerNeverWritesSecrets();
}

main();
