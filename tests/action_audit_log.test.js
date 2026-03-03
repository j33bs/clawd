'use strict';

// tests/action_audit_log.test.js — CSA CCM v4 LOG-09, SEF-04, AAC-02

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const assert = require('node:assert');
const zlib = require('node:zlib');

// ESM module — use dynamic import.
async function loadModule() {
  const { createActionAuditLog } = await import(
    '../workspace/runtime_hardening/src/action_audit_log.mjs'
  );
  return { createActionAuditLog };
}

function mkTempDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'action-audit-log-test-'));
}

async function main() {
  const { createActionAuditLog } = await loadModule();

  // ── Test 1: Basic write and hash chain verification ──────────────────────
  {
    const dir = mkTempDir();
    const logPath = path.join(dir, 'agent_actions.jsonl');
    const log = createActionAuditLog({ logPath });

    log.logAction({
      run_id: 'run-001',
      session_id: 'sess-001',
      action_class: 'A',
      tool_name: 'read_file',
      args_summary: 'path=/tmp/foo.txt',
      outcome: 'ok',
      reversible: true,
      operator_authorized: false
    });

    log.logAction({
      run_id: 'run-001',
      action_class: 'B',
      tool_name: 'write_file',
      args_summary: 'path=/workspace/bar.txt',
      outcome: 'ok',
      reversible: true,
      operator_authorized: false
    });

    assert.ok(fs.existsSync(logPath), 'log file must exist after logAction');

    const lines = fs.readFileSync(logPath, 'utf8').trim().split('\n');
    assert.strictEqual(lines.length, 2, 'must have written 2 lines');

    const entry0 = JSON.parse(lines[0]);
    const entry1 = JSON.parse(lines[1]);
    assert.ok(typeof entry0.integrity_hash === 'string' && entry0.integrity_hash.length === 64, 'entry 0 must have a 64-char integrity_hash');
    assert.ok(typeof entry1.integrity_hash === 'string' && entry1.integrity_hash.length === 64, 'entry 1 must have a 64-char integrity_hash');
    assert.notStrictEqual(entry0.integrity_hash, entry1.integrity_hash, 'hashes must differ');

    const verify = log.verifyChain(logPath);
    assert.ok(verify.ok, `chain must verify: ${JSON.stringify(verify)}`);
    assert.strictEqual(verify.verified, 2, 'must report 2 verified entries');
    assert.strictEqual(verify.firstBadLine, null);

    fs.rmSync(dir, { recursive: true, force: true });
    console.log('  PASS basic write + hash chain verification');
  }

  // ── Test 2: Tamper detection ──────────────────────────────────────────────
  {
    const dir = mkTempDir();
    const logPath = path.join(dir, 'agent_actions.jsonl');
    const log = createActionAuditLog({ logPath });

    log.logAction({
      run_id: 'run-002',
      action_class: 'D',
      tool_name: 'delete_file',
      args_summary: 'path=/tmp/secret.txt',
      outcome: 'ok',
      reversible: false,
      operator_authorized: true
    });

    // Tamper: overwrite the file's content with a modified entry.
    const original = fs.readFileSync(logPath, 'utf8');
    const tampered = original.replace('delete_file', 'read_file');
    fs.writeFileSync(logPath, tampered);

    const verify = log.verifyChain(logPath);
    assert.strictEqual(verify.ok, false, 'tampered log must fail chain verification');
    assert.strictEqual(verify.firstBadLine, 1, 'first bad line must be line 1');

    fs.rmSync(dir, { recursive: true, force: true });
    console.log('  PASS tamper detection');
  }

  // ── Test 3: Rotation trigger ──────────────────────────────────────────────
  {
    const dir = mkTempDir();
    const logPath = path.join(dir, 'agent_actions.jsonl');
    // Set a tiny rotation threshold (1 byte) to trigger rotation on first write.
    const log = createActionAuditLog({ logPath, maxFileBytes: 1 });

    // First write creates the file; file is 0 bytes before write so no rotation.
    log.logAction({
      run_id: 'run-003',
      action_class: 'A',
      tool_name: 'health_check',
      outcome: 'ok',
      reversible: true,
      operator_authorized: false
    });

    // Second write will see file >= 1 byte and rotate before writing.
    log.logAction({
      run_id: 'run-003',
      action_class: 'A',
      tool_name: 'health_check_2',
      outcome: 'ok',
      reversible: true,
      operator_authorized: false
    });

    // After rotation, the live log should contain only the second entry.
    const liveLines = fs.readFileSync(logPath, 'utf8').trim().split('\n').filter(Boolean);
    assert.strictEqual(liveLines.length, 1, 'after rotation, live log must have 1 entry');

    // Archive directory must exist and contain a .gz file.
    const archiveDir = path.join(dir, 'agent_actions_archive');
    assert.ok(fs.existsSync(archiveDir), 'archive dir must exist');
    const archives = fs.readdirSync(archiveDir).filter((f) => f.endsWith('.jsonl.gz'));
    assert.ok(archives.length >= 1, 'must have at least one archive file');

    // Decompress and verify the archived entry.
    const archivePath = path.join(archiveDir, archives[0]);
    const decompressed = zlib.gunzipSync(fs.readFileSync(archivePath)).toString('utf8');
    const archivedLines = decompressed.trim().split('\n').filter(Boolean);
    assert.ok(archivedLines.length >= 1, 'archive must contain at least one entry');

    fs.rmSync(dir, { recursive: true, force: true });
    console.log('  PASS rotation trigger');
  }

  // ── Test 4: Append-only — file size must not decrease after each logAction ─
  {
    const dir = mkTempDir();
    const logPath = path.join(dir, 'agent_actions.jsonl');
    const log = createActionAuditLog({ logPath, maxFileBytes: 10 * 1024 * 1024 });

    let prevSize = 0;
    for (let i = 0; i < 5; i++) {
      log.logAction({
        run_id: 'run-004',
        action_class: 'B',
        tool_name: `write_file_${i}`,
        outcome: 'ok',
        reversible: true,
        operator_authorized: false
      });
      const size = fs.statSync(logPath).size;
      assert.ok(size >= prevSize, `file size must not decrease (was ${prevSize}, now ${size})`);
      prevSize = size;
    }

    fs.rmSync(dir, { recursive: true, force: true });
    console.log('  PASS append-only enforcement (size monotonically increases)');
  }

  // ── Test 5: flush() is a no-op and does not throw ────────────────────────
  {
    const dir = mkTempDir();
    const log = createActionAuditLog({ logPath: path.join(dir, 'agent_actions.jsonl') });
    assert.doesNotThrow(() => log.flush(), 'flush() must not throw');
    fs.rmSync(dir, { recursive: true, force: true });
    console.log('  PASS flush() no-op');
  }

  // ── Test 6: getChainHead() updates with each write ───────────────────────
  {
    const dir = mkTempDir();
    const log = createActionAuditLog({ logPath: path.join(dir, 'agent_actions.jsonl') });
    const genesisHash = log.getChainHead();
    assert.strictEqual(genesisHash, '0'.repeat(64), 'initial chain head must be genesis hash');

    log.logAction({
      run_id: 'run-005',
      action_class: 'E',
      tool_name: 'api_call',
      outcome: 'ok',
      reversible: false,
      operator_authorized: false
    });

    const afterFirst = log.getChainHead();
    assert.notStrictEqual(afterFirst, genesisHash, 'chain head must change after first write');

    log.logAction({
      run_id: 'run-005',
      action_class: 'E',
      tool_name: 'api_call_2',
      outcome: 'ok',
      reversible: false,
      operator_authorized: false
    });

    const afterSecond = log.getChainHead();
    assert.notStrictEqual(afterSecond, afterFirst, 'chain head must change after second write');

    fs.rmSync(dir, { recursive: true, force: true });
    console.log('  PASS getChainHead() updates correctly');
  }

  console.log('PASS action_audit_log all tests');
}

main().catch((err) => {
  console.error('FAIL', err);
  process.exitCode = 1;
});
