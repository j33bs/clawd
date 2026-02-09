'use strict';

const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { buildSnapshotEvent } = require('../sys/audit/snapshot');
const { appendAuditEvent } = require('../sys/audit/logger');
const { computeEventHash } = require('../sys/audit/schema');

function pass(name) {
  console.log(`PASS ${name}`);
}

function testSnapshotDeterminismWithInjectedFields() {
  const options = {
    ts: 1739059200000,
    runId: 'snapshot-run',
    git: { branch: 'main', headSha: 'abc123', dirty: false },
    host: { platform: 'darwin', nodeVersion: 'v25.6.0' },
    config: { sysConfigHash: 'hash1', openclawConfigHash: 'hash2' },
    payload: { mode: 'test' }
  };

  const first = buildSnapshotEvent(options);
  const second = buildSnapshotEvent(options);
  assert.deepStrictEqual(first, second);
  assert.strictEqual(first.hash, computeEventHash(first));
  pass('snapshot event is deterministic with injected fields');
}

function testSnapshotWriteAndNoSecretLeak() {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'audit-snapshot-'));
  const logPath = path.join(tmpDir, 'audit.jsonl');

  const event = buildSnapshotEvent({
    ts: 1739059200000,
    runId: 'snapshot-run-2',
    git: { branch: 'main', headSha: 'abc123', dirty: false },
    host: { platform: 'darwin', nodeVersion: 'v25.6.0' },
    config: { sysConfigHash: 'hash1', openclawConfigHash: 'hash2' },
    payload: { token: 'sk-secret', info: 'safe' }
  });

  const result = appendAuditEvent(event, { enabled: true, logPath });
  assert.strictEqual(result.written, true);

  const line = fs.readFileSync(logPath, 'utf8').trim();
  assert.ok(line.length > 0);
  assert.ok(!line.includes('sk-secret'));
  assert.ok(line.includes('[REDACTED]'));
  pass('snapshot logging redacts secrets and appends event');
}

function main() {
  testSnapshotDeterminismWithInjectedFields();
  testSnapshotWriteAndNoSecretLeak();
}

main();
