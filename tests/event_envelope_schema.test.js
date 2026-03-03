'use strict';

const assert = require('node:assert/strict');
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

run('node event envelope has required keys and strips forbidden fields', () => {
  const helper = require(path.join(__dirname, '..', 'scripts', 'system2', 'event_envelope.js'));
  const env = helper.makeEnvelope({
    event: 'provider_diag_status',
    severity: 'warn',
    component: 'provider_diag',
    corr_id: 'diag-1',
    details: {
      prompt: 'secret',
      nested: { text: 'hidden', ok: true }
    },
    ts: '2026-02-23T01:10:00Z'
  });

  assert.equal(env.schema, helper.SCHEMA_ID);
  assert.equal(env.event, 'provider_diag_status');
  assert.equal(env.severity, 'WARN');
  assert.equal(env.component, 'provider_diag');
  assert.equal(env.corr_id, 'diag-1');
  assert.equal(helper.containsForbiddenKeys(env), false);
  assert.equal(env.details.nested.ok, true);
});

console.log('event_envelope_schema tests complete');
