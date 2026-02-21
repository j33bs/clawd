'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { createHash } = require('node:crypto');

const { createAuditSink } = require('../core/system2/security/audit_sink');

function sha256Hex(s) {
  return createHash('sha256').update(String(s), 'utf8').digest('hex');
}

function parseLines(p) {
  if (!fs.existsSync(p)) return [];
  const text = fs.readFileSync(p, 'utf8');
  return text
    .split('\n')
    .map((l) => l.trim())
    .filter((l) => l)
    .map((l) => JSON.parse(l));
}

async function testHashChainLinksAndPersistsAcrossRotation() {
  if (process.platform === 'win32') {
    console.log('SKIP audit hash chain perms on win32');
    return;
  }

  const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'openclaw-audit-chain-'));
  const auditPath = path.join(tmpRoot, 'edge.jsonl');

  const sink = createAuditSink({
    path: auditPath,
    rotateBytes: 200,
    keep: 2,
    hashChain: '1',
  });

  // First two writes should land in the same file then rotate.
  sink.writeLine(JSON.stringify({ ts_utc: 't1', request_id: 'r1', status: 200 }));
  sink.writeLine(JSON.stringify({ ts_utc: 't2', request_id: 'r2', status: 200 }));

  // Force a few more to cross the rotateBytes threshold.
  for (let i = 0; i < 10; i++) {
    sink.writeLine(JSON.stringify({ ts_utc: `t${i + 3}`, request_id: `r${i + 3}`, status: 200, pad: 'x'.repeat(50) }));
  }

  const main = parseLines(auditPath);
  const rotated = parseLines(auditPath + '.1');

  assert.ok(main.length > 0, 'main audit file should have lines');
  assert.ok(rotated.length > 0, 'rotated audit file should have lines');

  // Validate per-file linkage.
  function assertChain(lines) {
    for (let i = 0; i < lines.length; i++) {
      const e = lines[i];
      assert.ok(typeof e.prev_hash === 'string' && e.prev_hash.length === 64);
      assert.ok(typeof e.entry_hash === 'string' && e.entry_hash.length === 64);

      const base = { ...e };
      delete base.prev_hash;
      delete base.entry_hash;
      const expected = sha256Hex(e.prev_hash + '\n' + JSON.stringify(base));
      assert.equal(e.entry_hash, expected);

      if (i > 0) {
        assert.equal(e.prev_hash, lines[i - 1].entry_hash);
      }
    }
  }

  assertChain(rotated);
  assertChain(main);

  // Cross-rotation continuity: first line in main should link to last entry of rotated,
  // via the sidecar chain file.
  assert.equal(main[0].prev_hash, rotated[rotated.length - 1].entry_hash);

  const chainText = fs.readFileSync(sink.chainPath, 'utf8').trim();
  assert.equal(chainText, main[main.length - 1].entry_hash);
}

async function testTamperDetectionFailsClosed() {
  if (process.platform === 'win32') {
    console.log('SKIP audit hash chain tamper detection on win32');
    return;
  }

  const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'openclaw-audit-chain-tamper-'));
  const auditPath = path.join(tmpRoot, 'edge.jsonl');

  const sink = createAuditSink({
    path: auditPath,
    rotateBytes: 0,
    hashChain: '1',
  });

  sink.writeLine(JSON.stringify({ ts_utc: 't1', request_id: 'r1', status: 200 }));
  sink.writeLine(JSON.stringify({ ts_utc: 't2', request_id: 'r2', status: 200 }));

  const lines = fs.readFileSync(auditPath, 'utf8').trim().split('\n');
  const first = JSON.parse(lines[0]);
  first.status = 500; // mutate payload without repairing entry_hash
  lines[0] = JSON.stringify(first);
  fs.writeFileSync(auditPath, lines.join('\n') + '\n', 'utf8');

  assert.throws(
    () => createAuditSink({ path: auditPath, rotateBytes: 0, hashChain: '1' }),
    (err) => err && err.code === 'AUDIT_CHAIN_TAMPERED'
  );

  const tamperLog = auditPath + '.tamper.jsonl';
  assert.ok(fs.existsSync(tamperLog), 'tamper event log should be written');
  const tamperEntry = JSON.parse(fs.readFileSync(tamperLog, 'utf8').trim().split('\n')[0]);
  assert.equal(tamperEntry.event, 'audit_chain_tamper_detected');
}

async function main() {
  await testHashChainLinksAndPersistsAcrossRotation();
  await testTamperDetectionFailsClosed();
  console.log('PASS audit sink hash chaining persists across rotation');
}

main().catch((err) => {
  console.error(`FAIL audit_sink_hash_chain: ${err && err.message ? err.message : err}`);
  process.exitCode = 1;
});
