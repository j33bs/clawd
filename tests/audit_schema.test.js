'use strict';

const assert = require('node:assert');

const {
  REQUIRED_EVENT_FIELDS,
  createAuditEvent,
  validateEventShape,
  computeEventHash
} = require('../sys/audit/schema');

function pass(name) {
  console.log(`PASS ${name}`);
}

function testRequiredFields() {
  assert.ok(Array.isArray(REQUIRED_EVENT_FIELDS));
  for (const field of ['ts', 'eventType', 'runId', 'git', 'host', 'config', 'payload', 'hash']) {
    assert.ok(REQUIRED_EVENT_FIELDS.includes(field));
  }
  pass('required fields exported');
}

function testCreateAndValidateEvent() {
  const event = createAuditEvent({
    ts: 1739059200000,
    eventType: 'audit.snapshot',
    runId: 'run-123',
    git: { branch: 'main', headSha: 'abc123', dirty: false },
    host: { platform: 'darwin', nodeVersion: process.version },
    config: { sysConfigHash: 'deadbeef', openclawConfigHash: 'beadfeed' },
    payload: { check: 'ok' }
  });

  const result = validateEventShape(event);
  assert.strictEqual(result.ok, true);
  assert.deepStrictEqual(result.errors, []);
  assert.strictEqual(event.hash, computeEventHash(event));
  pass('event creation and validation');
}

function main() {
  testRequiredFields();
  testCreateAndValidateEvent();
}

main();
