#!/usr/bin/env node
'use strict';

const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const { redactIfSensitive } = require('../core/system2/inference/config');

const FIXTURES_DIR = path.resolve(__dirname, '..', 'fixtures', 'system2_federation_observability');

function loadJson(name) {
  return JSON.parse(fs.readFileSync(path.join(FIXTURES_DIR, name), 'utf8'));
}

function loadText(name) {
  return fs.readFileSync(path.join(FIXTURES_DIR, name), 'utf8');
}

function stableStringify(value) {
  if (value === null) return 'null';
  if (typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) {
    return '[' + value.map((v) => stableStringify(v)).join(',') + ']';
  }
  const keys = Object.keys(value).sort();
  return '{' + keys.map((k) => JSON.stringify(k) + ':' + stableStringify(value[k])).join(',') + '}';
}

function appendEventJsonl(event) {
  return stableStringify(event) + '\n';
}

function validateFederatedEnvelopeV1(obj) {
  const errors = [];
  function req(cond, msg) {
    if (!cond) errors.push(msg);
  }

  req(obj && typeof obj === 'object', 'envelope must be object');
  req(obj.type === 'federated_envelope_v1', 'type must be federated_envelope_v1');
  req(obj.version === '1', 'version must be 1');
  req(typeof obj.id === 'string' && obj.id.length > 0, 'id must be non-empty string');
  req(typeof obj.ts_utc === 'string' && obj.ts_utc.includes('T'), 'ts_utc must be ISO-like string');

  req(obj.routing && typeof obj.routing === 'object', 'routing must be object');
  if (obj.routing) {
    req(typeof obj.routing.from === 'string' && obj.routing.from.length > 0, 'routing.from required');
    req(typeof obj.routing.to === 'string' && obj.routing.to.length > 0, 'routing.to required');
    req(typeof obj.routing.topic === 'string' && obj.routing.topic.length > 0, 'routing.topic required');
    if (obj.routing.ttl_ms !== undefined) {
      req(Number.isFinite(obj.routing.ttl_ms), 'routing.ttl_ms must be number if present');
    }
  }

  req(obj.signature && typeof obj.signature === 'object', 'signature must be object');
  if (obj.signature) {
    req(typeof obj.signature.alg === 'string', 'signature.alg must be string');
    req(typeof obj.signature.key_id === 'string', 'signature.key_id must be string');
    req(typeof obj.signature.sig === 'string', 'signature.sig must be string');
  }

  req(obj.redaction && typeof obj.redaction === 'object', 'redaction must be object');
  if (obj.redaction) {
    req(typeof obj.redaction.applied === 'boolean', 'redaction.applied must be boolean');
    req(typeof obj.redaction.rules_version === 'string' && obj.redaction.rules_version.length > 0, 'redaction.rules_version required');
  }

  req(obj.payload !== undefined, 'payload required');

  return { ok: errors.length === 0, errors };
}

function validateSystem2EventV1(obj) {
  const errors = [];
  function req(cond, msg) {
    if (!cond) errors.push(msg);
  }

  req(obj && typeof obj === 'object', 'event must be object');
  req(obj.type === 'system2_event_v1', 'type must be system2_event_v1');
  req(obj.version === '1', 'version must be 1');
  req(typeof obj.ts_utc === 'string' && obj.ts_utc.includes('T'), 'ts_utc must be ISO-like string');
  req(typeof obj.event_type === 'string' && obj.event_type.length > 0, 'event_type required');
  req(['debug', 'info', 'warn', 'error'].includes(obj.level), 'level must be one of debug|info|warn|error');
  req(obj.payload && typeof obj.payload === 'object', 'payload must be object');
  req(obj.context && typeof obj.context === 'object', 'context must be object');

  return { ok: errors.length === 0, errors };
}

function deepRedact(value, keyName) {
  if (value === null) return null;
  if (typeof value === 'string') {
    if (typeof keyName === 'string' && keyName.length > 0) {
      return redactIfSensitive(keyName, value);
    }
    return value;
  }
  if (typeof value !== 'object') return value;
  if (Array.isArray(value)) return value.map((v) => deepRedact(v, keyName));

  const out = {};
  for (const k of Object.keys(value)) {
    out[k] = deepRedact(value[k], k);
  }
  return out;
}

function makeEmitter(options) {
  const enabled = options && options.enabled === true;
  const strict = options && options.strict === true;
  const sink = options && options.sink;

  return async function emitSystem2Event(eventType, payload, context) {
    if (!enabled) return;

    const event = {
      type: 'system2_event_v1',
      version: '1',
      ts_utc: '2026-02-13T00:00:00.000Z',
      event_type: String(eventType || ''),
      level: 'info',
      payload: deepRedact(payload || {}, 'payload'),
      context: context || {}
    };

    if (!sink || typeof sink.appendEvent !== 'function') {
      if (strict) {
        const err = new Error('sink missing');
        err.code = 'SINK_MISSING';
        throw err;
      }
      return;
    }

    try {
      await sink.appendEvent(event);
    } catch (err) {
      if (strict) throw err;
    }
  };
}

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
  const emit = makeEmitter({ enabled: false, strict: true, sink });
  await emit('x', { authorization: 'sensitive_value' }, {});
  assert.strictEqual(calls.length, 0);
});

test('gating: enabled emitter appends a redacted event', async function () {
  const calls = [];
  const sink = { appendEvent: async (evt) => calls.push(evt) };
  const emit = makeEmitter({ enabled: true, strict: true, sink });
  await emit('system2_redaction_probe', { authorization: 'sensitive_value', safe_field: 'safe_value' }, { run_id: 'run_0003' });
  assert.strictEqual(calls.length, 1);
  assert.strictEqual(calls[0].payload.authorization, '[REDACTED]');
  assert.strictEqual(calls[0].payload.safe_field, 'safe_value');
});

test('emitter does not throw on sink error by default (strict=false)', async function () {
  const sink = { appendEvent: async () => { throw new Error('sink failure'); } };
  const emit = makeEmitter({ enabled: true, strict: false, sink });
  await emit('x', {}, {});
});

test('emitter fails closed on sink error when strict=true', async function () {
  const sink = { appendEvent: async () => { throw new Error('sink failure'); } };
  const emit = makeEmitter({ enabled: true, strict: true, sink });
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

