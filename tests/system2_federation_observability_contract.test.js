#!/usr/bin/env node
'use strict';

const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const { validateFederatedEnvelopeV1 } = require('../core/system2/federation/envelope_v1');
const { validateSystem2EventV1 } = require('../core/system2/observability/event_v1');
const { appendEventJsonl } = require('../core/system2/observability/jsonl_sink');
const { deepRedact } = require('../core/system2/observability/redaction');
const { makeEmitter } = require('../core/system2/observability/emitter');

const FIXTURES_DIR = path.resolve(__dirname, '..', 'fixtures', 'system2_federation_observability');

function loadJson(name) {
  return JSON.parse(fs.readFileSync(path.join(FIXTURES_DIR, name), 'utf8'));
}

function loadText(name) {
  return fs.readFileSync(path.join(FIXTURES_DIR, name), 'utf8');
}

const FIXED_NOW = () => new Date('2026-02-13T00:00:00.000Z');

const tests = [];
function test(name, fn) {
  tests.push({ name, fn });
}

test('FederatedEnvelopeV1 fixture validates (strict)', function () {
  const env = loadJson('envelope_v1.json');
  const result = validateFederatedEnvelopeV1(env);
  assert.strictEqual(result.ok, true, result.errors.join('; '));
});

test('FederatedEnvelopeV1 rejects invalid schema (fail-closed)', function () {
  const bad = { type: 'federated_envelope_v1', version: '1' };
  const result = validateFederatedEnvelopeV1(bad);
  assert.strictEqual(result.ok, false);
  assert.ok(result.errors.length > 0);
});

test('System2EventV1 fixture validates', function () {
  const evt = loadJson('event_v1.json');
  const result = validateSystem2EventV1(evt);
  assert.strictEqual(result.ok, true, result.errors.join('; '));
});

test('JSONL sink contract is deterministic (exact line match)', function () {
  const evt = loadJson('event_v1.json');
  const expected = loadText('event_v1.expected.jsonl');
  const line = appendEventJsonl(evt);
  assert.strictEqual(line, expected);
});

test('redaction-at-write is deterministic and idempotent', function () {
  const input = loadJson('redaction_input.json');
  const expected = loadJson('redaction_expected.json');
  const once = deepRedact(input);
  const twice = deepRedact(once);
  assert.deepStrictEqual(once, expected);
  assert.deepStrictEqual(twice, expected);
});

test('gating: disabled emitter is a no-op', async function () {
  const calls = [];
  const sink = { appendEvent: async (evt) => calls.push(evt) };
  const emit = makeEmitter({ enabled: false, strict: true, sink, nowFn: FIXED_NOW });
  await emit('x', { authorization: 'sensitive_value' }, {});
  assert.strictEqual(calls.length, 0);
});

test('gating: enabled emitter appends a redacted event', async function () {
  const calls = [];
  const sink = { appendEvent: async (evt) => calls.push(evt) };
  const emit = makeEmitter({ enabled: true, strict: true, sink, nowFn: FIXED_NOW });
  await emit('system2_redaction_probe', { authorization: 'sensitive_value', safe_field: 'safe_value' }, { run_id: 'run_0003' });
  assert.strictEqual(calls.length, 1);
  assert.strictEqual(calls[0].payload.authorization, '[REDACTED]');
  assert.strictEqual(calls[0].payload.safe_field, 'safe_value');
});

test('emitter does not throw on sink error by default (strict=false)', async function () {
  const sink = { appendEvent: async () => { throw new Error('sink failure'); } };
  const emit = makeEmitter({ enabled: true, strict: false, sink, nowFn: FIXED_NOW });
  await emit('x', {}, {});
});

test('emitter fails closed on sink error when strict=true', async function () {
  const sink = { appendEvent: async () => { throw new Error('sink failure'); } };
  const emit = makeEmitter({ enabled: true, strict: true, sink, nowFn: FIXED_NOW });
  let threw = false;
  try {
    await emit('x', {}, {});
  } catch (err) {
    threw = true;
    assert.strictEqual(err.message, 'sink failure');
  }
  assert.strictEqual(threw, true);
});

async function run() {
  for (const t of tests) {
    try {
      await t.fn();
      console.log('PASS ' + t.name);
    } catch (err) {
      console.error('FAIL ' + t.name + ': ' + err.message);
      process.exitCode = 1;
    }
  }
}

run();
