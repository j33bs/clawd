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
    if (/^[0-9a-f]{64}$/i.test(h)) return h.toLowerCase();
  } catch (_) {}
  return '0'.repeat(64);
}

function writeChainHash(chainPath, h) {
  const s = String(h || '').trim().toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(s)) return;
  fs.writeFileSync(chainPath, s + '\n', { encoding: 'utf8', mode: 0o600 });
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
};
