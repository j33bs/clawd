#!/usr/bin/env node
'use strict';

const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { captureSnapshot } = require('../scripts/system2_snapshot_capture');

function test(name, fn) {
  try {
    fn();
    console.log('PASS ' + name);
  } catch (err) {
    console.error('FAIL ' + name + ': ' + err.message);
    process.exitCode = 1;
  }
}

function loadFixture(name) {
  return fs.readFileSync(path.resolve(__dirname, '..', 'fixtures', 'system2_snapshot', name), 'utf8');
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

test('captureSnapshot writes stable files and summary shape', function () {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'clawd-snapshot-'));
  const now = '2026-02-12T00:00:00.000Z';

  const result = captureSnapshot({
    outDir: tempDir,
    maxLogLines: 500,
    runner: makeFixtureRunner(),
    now: function fixedNow() { return now; }
  });

  assert.strictEqual(result.ok, true, 'snapshot should be ok');
  assert.strictEqual(result.summary.timestamp_utc, now, 'timestamp should be stable when injected');
  assert.strictEqual(result.summary.openclaw_version, 'openclaw 0.9.1');
  assert.strictEqual(result.summary.health_ok, true);
  assert.strictEqual(result.summary.status_ok, true);
  assert.strictEqual(result.summary.approvals_count, 2);
  assert.strictEqual(result.summary.nodes_paired, 1);
  assert.strictEqual(result.summary.nodes_pending, 2);
  assert.ok(result.summary.log_signature_counts.auth_error >= 1, 'auth signature count expected');
  assert.ok(result.summary.log_signature_counts.module_not_found >= 1, 'module_not_found count expected');
  assert.deepStrictEqual(result.summary.commands_failed, []);

  assert.ok(fs.existsSync(path.join(tempDir, 'health.json')), 'parsed health json should exist');
  assert.ok(fs.existsSync(path.join(tempDir, 'status.meta.json')), 'status meta should exist');
  assert.ok(fs.existsSync(path.join(tempDir, 'snapshot_summary.json')), 'summary file should exist');

  fs.rmSync(tempDir, { recursive: true, force: true });
});

test('captureSnapshot fail-closed with partial outputs when command fails', function () {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'clawd-snapshot-fail-'));

  const result = captureSnapshot({
    outDir: tempDir,
    maxLogLines: 500,
    runner: makeFixtureRunner({
      nodes: { status: 1, stdout: '', stderr: 'permission denied' }
    })
  });

  assert.strictEqual(result.ok, false, 'snapshot should fail when a command fails');
  assert.ok(result.summary.commands_failed.includes('nodes'), 'failed command should be tracked');
  assert.ok(fs.existsSync(path.join(tempDir, 'nodes.stderr.txt')), 'stderr output should be captured');
  assert.ok(fs.existsSync(path.join(tempDir, 'snapshot_summary.json')), 'summary should still be written');

  fs.rmSync(tempDir, { recursive: true, force: true });
});
