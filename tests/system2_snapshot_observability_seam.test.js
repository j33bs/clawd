#!/usr/bin/env node
'use strict';

const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { captureSnapshot } = require('../scripts/system2_snapshot_capture');
const { stableStringify } = require('../core/system2/canonical_json');

const FIXTURES_DIR = path.resolve(__dirname, '..', 'fixtures', 'system2_snapshot');

function loadFixture(name) {
  return fs.readFileSync(path.join(FIXTURES_DIR, name), 'utf8');
}

function makeFixtureRunner(overrides = {}) {
  const map = {
    openclaw_version: loadFixture('version.txt'),
    health: loadFixture('health.json'),
    status: loadFixture('status.json'),
    approvals: loadFixture('approvals.json'),
    nodes: loadFixture('nodes.json')
  };

  return function fixtureRunner(spec) {
    if (overrides[spec.id]) {
      return overrides[spec.id];
    }
    return { status: 0, stdout: map[spec.id], stderr: '' };
  };
}

function nextTick() {
  return new Promise((resolve) => setImmediate(resolve));
}

const tests = [];
function test(name, fn) {
  tests.push({ name, fn });
}

test('OFF: system2.observability.enabled=false emits nothing and writes no JSONL', async function () {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'clawd-obs-off-'));
  const obsPath = path.join(tempDir, 'obs.jsonl');

  const result = captureSnapshot({
    outDir: tempDir,
    maxLogLines: 50,
    runner: makeFixtureRunner(),
    now: function fixedNow() { return '2026-02-12T00:00:00.000Z'; },
    system2: {
      observability: {
        enabled: false,
        jsonlPath: obsPath
      }
    }
  });

  assert.strictEqual(result.ok, true);
  await nextTick();
  assert.strictEqual(fs.existsSync(obsPath), false, 'obs jsonl must not be created when disabled');

  fs.rmSync(tempDir, { recursive: true, force: true });
});

test('ON: system2.observability.enabled=true writes exactly one deterministic JSONL line', async function () {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'clawd-obs-on-'));
  const obsPath = path.join(tempDir, 'observability', 'events.jsonl');
  fs.mkdirSync(path.dirname(obsPath), { recursive: true });

  const warns = [];
  const result = captureSnapshot({
    outDir: tempDir,
    maxLogLines: 50,
    runner: makeFixtureRunner(),
    now: function fixedNow() { return '2026-02-12T00:00:00.000Z'; },
    warn: function warn(msg) { warns.push(String(msg)); },
    system2: {
      observability: {
        enabled: true,
        jsonlPath: obsPath,
        extraPayload: {
          authorization: 'sensitive_value',
          safe_field: 'safe_value'
        }
      }
    }
  });

  assert.strictEqual(result.ok, true);
  await nextTick();
  assert.deepStrictEqual(warns, []);

  assert.strictEqual(fs.existsSync(obsPath), true, 'obs jsonl must exist when enabled');
  const raw = fs.readFileSync(obsPath, 'utf8');
  const lines = raw.split('\n').filter(Boolean);
  assert.strictEqual(lines.length, 1, 'expected exactly one JSONL line');

  const parsed = JSON.parse(lines[0]);
  assert.strictEqual(parsed.type, 'system2_event_v1');
  assert.strictEqual(parsed.version, '1');
  assert.strictEqual(parsed.ts_utc, result.summary.timestamp_utc);
  assert.strictEqual(parsed.event_type, 'system2_snapshot_captured');
  assert.strictEqual(parsed.level, 'info');
  assert.strictEqual(parsed.context && parsed.context.subsystem, 'system2_snapshot_capture');
  assert.strictEqual(parsed.payload.authorization, '[REDACTED]');
  assert.strictEqual(parsed.payload.safe_field, 'safe_value');

  const expectedEvent = {
    type: 'system2_event_v1',
    version: '1',
    ts_utc: result.summary.timestamp_utc,
    event_type: 'system2_snapshot_captured',
    level: 'info',
    payload: {
      authorization: '[REDACTED]',
      commands_failed: [],
      log_signature_counts: result.summary.log_signature_counts,
      safe_field: 'safe_value',
      snapshot_ok: true
    },
    context: { subsystem: 'system2_snapshot_capture' }
  };

  assert.strictEqual(raw, stableStringify(expectedEvent) + '\n');

  fs.rmSync(tempDir, { recursive: true, force: true });
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
