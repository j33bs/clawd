#!/usr/bin/env node
'use strict';

const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { captureSnapshot } = require('./system2_snapshot_capture');

const EXPECTED_COMMAND_IDS = [
  'openclaw_version',
  'health',
  'status',
  'approvals',
  'nodes'
];

function loadFixture(name) {
  return fs.readFileSync(path.resolve(__dirname, '..', 'fixtures', 'system2_snapshot', name), 'utf8');
}

function makeFixtureRunner(calls) {
  const map = {
    openclaw_version: loadFixture('version.txt'),
    health: loadFixture('health.json'),
    status: loadFixture('status.json'),
    approvals: loadFixture('approvals.json'),
    nodes: loadFixture('nodes.json')
  };

  return function fixtureRunner(spec) {
    calls.push({ id: spec.id, cmd: spec.cmd });
    return { status: 0, stdout: map[spec.id] || '', stderr: '' };
  };
}

function main() {
  const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'clawd-system2-obs-smoke-'));
  const jsonlDir = path.join(tmpRoot, 'observability');
  const jsonlPath = path.join(jsonlDir, 'events.jsonl');

  // Parent dir must exist; seam must fail-closed (no mkdir) if it doesn't.
  fs.mkdirSync(jsonlDir, { recursive: true });

  const runnerCalls = [];
  const fixedNow = '2026-02-12T00:00:00.000Z';

  try {
    const result = captureSnapshot({
      outDir: tmpRoot,
      maxLogLines: 50,
      runner: makeFixtureRunner(runnerCalls),
      now: function fixedNowFn() { return fixedNow; },
      warn: function warnFn() {}, // suppress warnings in smoke output
      system2: {
        observability: {
          enabled: true,
          jsonlPath,
          extraPayload: {
            authorization: 'sensitive_value'
          }
        }
      }
    });

    assert.strictEqual(result && typeof result === 'object', true, 'captureSnapshot must return an object');
    assert.strictEqual(result.ok, true, 'snapshot should be ok under fixtures');
    assert.strictEqual(result.summary.timestamp_utc, fixedNow, 'snapshot timestamp should be deterministic when injected');

    // Ensure we used the fixture runner (no external commands executed by this script).
    assert.ok(runnerCalls.length > 0, 'fixture runner should have been invoked');
    const seen = new Set(runnerCalls.map((c) => c.id));
    for (const id of EXPECTED_COMMAND_IDS) {
      assert.ok(seen.has(id), `expected runner to be invoked for: ${id}`);
    }

    assert.strictEqual(fs.existsSync(jsonlPath), true, 'expected JSONL file to exist when enabled');
    const raw = fs.readFileSync(jsonlPath, 'utf8');
    const lines = raw.split('\n').filter(Boolean);
    assert.strictEqual(lines.length, 1, 'expected exactly one JSONL line');

    const evt = JSON.parse(lines[0]);
    assert.strictEqual(evt.event_type, 'system2_snapshot_captured');
    assert.strictEqual(evt.ts_utc, result.summary.timestamp_utc);
    assert.strictEqual(evt.payload && evt.payload.authorization, '[REDACTED]');

    // No networking: this smoke uses a fixture runner, and the seam is local append-only.
    console.log('SMOKE PASS: system2_snapshot_capture observability seam');
  } catch (err) {
    console.error('SMOKE FAIL: system2_snapshot_capture observability seam');
    console.error(String(err && err.message ? err.message : err));
    process.exitCode = 1;
  } finally {
    try {
      fs.rmSync(tmpRoot, { recursive: true, force: true });
    } catch (_) {}
  }
}

if (require.main === module) {
  main();
}
