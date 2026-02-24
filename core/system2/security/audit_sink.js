'use strict';

/**
 * Append-only JSONL audit sink with simple size-based rotation.
 *
 * - Never logs secrets; caller must ensure event objects contain only metadata.
 * - No network. Deterministic file writes only.
 */

const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { createHash } = require('node:crypto');

function defaultAuditPath() {
  return path.join(os.homedir(), '.openclaw', 'audit', 'edge.jsonl');
}

function isSha256Hex(value) {
  return /^[0-9a-f]{64}$/.test(String(value || '').trim().toLowerCase());
}

function sha256Hex(s) {
  return createHash('sha256').update(String(s), 'utf8').digest('hex');
}

function require0600RegularFile(filePath, { strictPerms } = {}) {
  const p = String(filePath || '');
  if (!p) return;
  let st;
  try {
    st = fs.lstatSync(p);
  } catch (_) {
    return; // does not exist
  }
  if (!st.isFile()) {
    const err = new Error(`audit chain file must be a regular file: ${p}`);
    err.code = 'AUDIT_CHAIN_NOT_REGULAR';
    throw err;
  }
  if (typeof st.isSymbolicLink === 'function' && st.isSymbolicLink()) {
    const err = new Error(`audit chain file must not be a symlink: ${p}`);
    err.code = 'AUDIT_CHAIN_SYMLINK';
    throw err;
  }
  if (strictPerms) {
    const mode = st.mode & 0o777;
    if (mode !== 0o600) {
      const err = new Error(`audit chain file must have permissions 0600: ${p}`);
      err.code = 'AUDIT_CHAIN_BAD_MODE';
      throw err;
    }
  }
}

function ensureChainFile(chainPath, { strictPerms } = {}) {
  require0600RegularFile(chainPath, { strictPerms });
  if (fs.existsSync(chainPath)) return;
  const fd = fs.openSync(chainPath, 'wx', 0o600);
  try {
    fs.writeFileSync(fd, '0'.repeat(64) + '\n', { encoding: 'utf8' });
  } finally {
    try { fs.closeSync(fd); } catch (_) {}
  }
}

function readChainHash(chainPath) {
  try {
    const s = fs.readFileSync(chainPath, 'utf8');
    const h = String(s || '').trim();
    if (isSha256Hex(h)) return h.toLowerCase();
  } catch (_) {}
  return '0'.repeat(64);
}

function readChainHashStrict(chainPath) {
  let raw;
  try {
    raw = fs.readFileSync(chainPath, 'utf8');
  } catch (error) {
    const err = new Error(`audit chain file unreadable: ${chainPath}`);
    err.code = 'AUDIT_CHAIN_READ_ERROR';
    err.cause = error;
    throw err;
  }
  const chainHash = String(raw || '').trim().toLowerCase();
  if (!isSha256Hex(chainHash)) {
    const err = new Error(`audit chain file invalid hash: ${chainPath}`);
    err.code = 'AUDIT_CHAIN_INVALID_HASH';
    throw err;
  }
  return chainHash;
}

function writeChainHash(chainPath, h) {
  const s = String(h || '').trim().toLowerCase();
  if (!isSha256Hex(s)) return;
  fs.writeFileSync(chainPath, s + '\n', { encoding: 'utf8', mode: 0o600 });
}

function verifyHashChainFile(filePath, chainPath, opts = {}) {
  const emitTamperEvent = typeof opts.emitTamperEvent === 'function'
    ? opts.emitTamperEvent
    : () => {};
  const failTamper = (reason, detail = {}) => {
    const payload = { reason, ...detail };
    try {
      emitTamperEvent(payload);
    } catch (_) {}
    const err = new Error(`audit hash chain verification failed: ${reason}`);
    err.code = 'AUDIT_CHAIN_TAMPERED';
    err.detail = payload;
    throw err;
  };

  let lines = [];
  if (fs.existsSync(filePath)) {
    const raw = fs.readFileSync(filePath, 'utf8');
    lines = String(raw || '')
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean);
  }

  let expectedPrev = '0'.repeat(64);
  for (let i = 0; i < lines.length; i += 1) {
    const lineNo = i + 1;
    let obj;
    try {
      obj = JSON.parse(lines[i]);
    } catch (_) {
      failTamper('invalid_json', { line: lineNo });
    }

    if (!obj || typeof obj !== 'object' || Array.isArray(obj)) {
      failTamper('invalid_record_shape', { line: lineNo });
    }
    if (!isSha256Hex(obj.prev_hash) || !isSha256Hex(obj.entry_hash)) {
      failTamper('invalid_hash_shape', { line: lineNo });
    }
    if (String(obj.prev_hash).toLowerCase() !== expectedPrev) {
      failTamper('prev_hash_mismatch', {
        line: lineNo,
        expected_prev_hash: expectedPrev,
        actual_prev_hash: String(obj.prev_hash).toLowerCase()
      });
    }

    const base = { ...obj };
    delete base.prev_hash;
    delete base.entry_hash;
    const expectedEntryHash = sha256Hex(expectedPrev + '\n' + JSON.stringify(base));
    if (String(obj.entry_hash).toLowerCase() !== expectedEntryHash) {
      failTamper('entry_hash_mismatch', {
        line: lineNo,
        expected_entry_hash: expectedEntryHash,
        actual_entry_hash: String(obj.entry_hash).toLowerCase()
      });
    }
    expectedPrev = expectedEntryHash;
  }

  const chainHash = readChainHashStrict(chainPath);
  if (chainHash !== expectedPrev) {
    failTamper('chain_tip_mismatch', {
      expected_chain_hash: expectedPrev,
      actual_chain_hash: chainHash
    });
  }

  return {
    ok: true,
    entries: lines.length,
    chainHash
  };
}

function appendTamperEvent(filePath, detail) {
  const eventPath = filePath + '.tamper.jsonl';
  const event = {
    ts_utc: new Date().toISOString(),
    event: 'audit_chain_tamper_detected',
    detail: detail || {}
  };
  fs.appendFileSync(eventPath, JSON.stringify(event) + '\n', { encoding: 'utf8' });
}

function rotateIfNeeded(filePath, rotateBytes, keep) {
  if (!rotateBytes || rotateBytes <= 0) return;
  let st;
  try {
    st = fs.statSync(filePath);
  } catch (_) {
    return; // file does not exist yet
  }
  if (!st || !st.isFile()) return;
  if (st.size < rotateBytes) return;

  const n = Math.max(1, keep || 5);
  for (let i = n - 1; i >= 1; i--) {
    const src = `${filePath}.${i}`;
    const dst = `${filePath}.${i + 1}`;
    try {
      if (fs.existsSync(src)) fs.renameSync(src, dst);
    } catch (_) {}
  }
  try {
    fs.renameSync(filePath, `${filePath}.1`);
  } catch (_) {}
}

function createAuditSink(opts = {}) {
  const filePath = String(opts.path || defaultAuditPath());
  const rotateBytes = Number.isFinite(Number(opts.rotateBytes)) ? Number(opts.rotateBytes) : 10_000_000;
  const keep = Number.isFinite(Number(opts.keep)) ? Number(opts.keep) : 5;
  const hashChainEnabled = String(opts.hashChain || '') === '1';
  const strictPerms = process.platform !== 'win32';

  const dir = path.dirname(filePath);
  try {
    fs.mkdirSync(dir, { recursive: true });
  } catch (_) {}

  const chainPath = filePath + '.chain';
  if (hashChainEnabled) {
    ensureChainFile(chainPath, { strictPerms });
    verifyHashChainFile(filePath, chainPath, {
      emitTamperEvent(detail) {
        appendTamperEvent(filePath, detail);
      }
    });
  }

  function writeLine(line) {
    // Fail-closed: never write potentially sensitive markers.
    const s = String(line || '');
    if (!s) return;
    if (s.includes('Bearer ')) return;

    rotateIfNeeded(filePath, rotateBytes, keep);
    if (!hashChainEnabled) {
      fs.appendFileSync(filePath, s + '\n', { encoding: 'utf8' });
      return;
    }

    let obj;
    try {
      obj = JSON.parse(s);
    } catch (_) {
      // If the caller isn't sending JSON, do not write in hash-chain mode.
      return;
    }
    if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return;

    const prev = readChainHash(chainPath);
    const base = { ...obj };
    delete base.prev_hash;
    delete base.entry_hash;
    const payload = JSON.stringify(base);
    const entryHash = sha256Hex(prev + '\n' + payload);
    const out = { ...base, prev_hash: prev, entry_hash: entryHash };

    fs.appendFileSync(filePath, JSON.stringify(out) + '\n', { encoding: 'utf8' });
    writeChainHash(chainPath, entryHash);
  }

  return { filePath, writeLine, chainPath };
}

module.exports = {
  createAuditSink,
  defaultAuditPath,
  verifyHashChainFile,
};
