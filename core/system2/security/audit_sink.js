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

function defaultAuditPath() {
  return path.join(os.homedir(), '.openclaw', 'audit', 'edge.jsonl');
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

  const dir = path.dirname(filePath);
  try {
    fs.mkdirSync(dir, { recursive: true });
  } catch (_) {}

  function writeLine(line) {
    // Fail-closed: never write potentially sensitive markers.
    const s = String(line || '');
    if (!s) return;
    if (s.includes('Bearer ')) return;

    rotateIfNeeded(filePath, rotateBytes, keep);
    fs.appendFileSync(filePath, s + '\n', { encoding: 'utf8' });
  }

  return { filePath, writeLine };
}

module.exports = {
  createAuditSink,
  defaultAuditPath,
};

