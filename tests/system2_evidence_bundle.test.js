#!/usr/bin/env node
'use strict';

const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { buildEvidenceBundle } = require('../scripts/system2_evidence_bundle');

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

function makeSnapshotRunner(overrides = {}) {
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

test('buildEvidenceBundle captures raw, writes redacted output, and emits manifest', function () {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), 'clawd-evidence-'));

  const result = buildEvidenceBundle({
    outDir,
    maxBytes: 1024 * 1024,
    maxLogLines: 500,
    snapshotRunner: makeSnapshotRunner()
  });

  assert.strictEqual(result.ok, true, 'bundle should be successful');
  assert.strictEqual(result.summary.snapshot_ok, true, 'summary snapshot_ok should be true');
  assert.ok(result.summary.manifest_file_count > 0, 'manifest should include files');
  assert.ok(fs.existsSync(path.join(outDir, 'manifest.json')), 'manifest should be written');

  const rawStatus = fs.readFileSync(path.join(outDir, 'raw', 'status.stdout.txt'), 'utf8');
  const redactedStatus = fs.readFileSync(path.join(outDir, 'redacted', 'status.stdout.txt'), 'utf8');

  assert.ok(rawStatus.includes('sk-TEST1234567890ABCDE'), 'raw output should preserve synthetic token');
  assert.ok(!redactedStatus.includes('sk-TEST1234567890ABCDE'), 'redacted output should remove synthetic token');
  assert.ok(!redactedStatus.includes('/Users/demo'), 'redacted output should remove absolute path');
  assert.ok(redactedStatus.includes('{{SECRET_TOKEN}}'), 'redacted output should include placeholder');
  assert.ok(result.summary.redaction_summary.replacements_total > 0, 'redaction counts should be nonzero');

  fs.rmSync(outDir, { recursive: true, force: true });
});

test('buildEvidenceBundle preserves fail-closed snapshot status', function () {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), 'clawd-evidence-fail-'));

  const result = buildEvidenceBundle({
    outDir,
    maxBytes: 1024 * 1024,
    maxLogLines: 500,
    snapshotRunner: makeSnapshotRunner({
      health: { status: 1, stdout: '', stderr: 'health command failed' }
    })
  });

  assert.strictEqual(result.ok, false, 'bundle should be marked failed when snapshot fails');
  assert.strictEqual(result.summary.snapshot_ok, false, 'summary should report snapshot failure');
  assert.ok(result.summary.snapshot_summary.commands_failed.includes('health'), 'health should be in failed commands');
  assert.ok(fs.existsSync(path.join(outDir, 'manifest.json')), 'manifest should still be emitted');

  fs.rmSync(outDir, { recursive: true, force: true });
});
