/**
 * action_audit_log.mjs — CSA CCM v4 LOG-09, SEF-04, AAC-02
 *
 * Append-only JSONL audit log for autonomous agent actions.
 * Each entry is hash-chained (SHA-256) for tamper detection.
 * Rotation: archive to .gz when file exceeds MAX_FILE_BYTES (50 MB).
 */

import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';

const DEFAULT_LOG_PATH = path.resolve(
  process.env.ACTION_AUDIT_LOG_PATH ||
    path.join(process.cwd(), 'workspace', 'audit', 'agent_actions.jsonl')
);
const MAX_FILE_BYTES = 50 * 1024 * 1024; // 50 MB

/**
 * Compute SHA-256 hex digest of a string.
 * @param {string} input
 * @returns {string}
 */
function sha256(input) {
  return crypto.createHash('sha256').update(String(input), 'utf8').digest('hex');
}

/**
 * Return YYYYMM string for archive filename.
 * @param {Date} date
 * @returns {string}
 */
function yyyymm(date) {
  const y = date.getUTCFullYear();
  const m = String(date.getUTCMonth() + 1).padStart(2, '0');
  return `${y}${m}`;
}

/**
 * Append a single JSONL line to a file synchronously.
 * Opens in append mode (O_WRONLY | O_CREAT | O_APPEND) — never seeks.
 * @param {string} filePath
 * @param {string} line
 */
function appendLine(filePath, line) {
  // Ensure directory exists.
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.appendFileSync(filePath, line + '\n', { encoding: 'utf8', flag: 'a' });
}

/**
 * Create an ActionAuditLog instance.
 *
 * @param {object} [opts]
 * @param {string} [opts.logPath]        — path to agent_actions.jsonl
 * @param {number} [opts.maxFileBytes]   — rotation threshold in bytes
 * @returns {ActionAuditLog}
 */
function createActionAuditLog(opts = {}) {
  const logPath = opts.logPath || DEFAULT_LOG_PATH;
  const maxFileBytes = typeof opts.maxFileBytes === 'number' ? opts.maxFileBytes : MAX_FILE_BYTES;
  const archiveDir = path.join(path.dirname(logPath), 'agent_actions_archive');

  let prevHash = '0'.repeat(64); // genesis hash
  let _pendingFlush = null;

  /**
   * Compute current file size without stat-ing on every write.
   */
  function currentFileBytes() {
    try {
      return fs.statSync(logPath).size;
    } catch {
      return 0;
    }
  }

  /**
   * Archive the current log file to YYYYMM.jsonl.gz, then truncate.
   */
  function rotate() {
    const now = new Date();
    const tag = yyyymm(now);
    fs.mkdirSync(archiveDir, { recursive: true });
    const archivePath = path.join(archiveDir, `${tag}.jsonl.gz`);

    const src = fs.readFileSync(logPath);
    const compressed = zlib.gzipSync(src);

    // If an archive for this month already exists, append (concatenated gzip streams are valid).
    fs.appendFileSync(archivePath, compressed);

    // Truncate the live log.
    fs.writeFileSync(logPath, '', { encoding: 'utf8', flag: 'w' });
    // Reset hash chain.
    prevHash = '0'.repeat(64);
  }

  /**
   * Log a single autonomous agent action.
   *
   * @param {object} entry
   * @param {string} entry.run_id               — unique ID for the autonomous run
   * @param {string} [entry.session_id]         — session ID if applicable
   * @param {'A'|'B'|'C'|'D'|'E'} entry.action_class
   * @param {string} entry.tool_name            — name of the tool/action
   * @param {string} [entry.args_summary]       — brief, redacted description of arguments
   * @param {'ok'|'error'|'denied'|'tripped'} entry.outcome
   * @param {boolean} [entry.reversible]        — whether the action is reversible
   * @param {boolean} [entry.operator_authorized] — whether operator pre-authorized this action
   * @param {string} [entry.error_message]      — error detail if outcome is 'error'
   */
  function logAction(entry) {
    const ts = new Date().toISOString();
    const record = {
      ts,
      run_id: String(entry.run_id || 'unknown'),
      session_id: entry.session_id ? String(entry.session_id) : undefined,
      action_class: entry.action_class,
      tool_name: String(entry.tool_name || 'unknown'),
      args_summary: entry.args_summary ? String(entry.args_summary).slice(0, 512) : undefined,
      outcome: entry.outcome,
      reversible: Boolean(entry.reversible ?? true),
      operator_authorized: Boolean(entry.operator_authorized ?? false),
      error_message: entry.error_message ? String(entry.error_message).slice(0, 256) : undefined
    };
    // Remove undefined fields.
    for (const key of Object.keys(record)) {
      if (record[key] === undefined) delete record[key];
    }

    const entryJson = JSON.stringify(record);
    const integrityHash = sha256(prevHash + entryJson);
    prevHash = integrityHash;

    const line = JSON.stringify({ ...record, integrity_hash: integrityHash });

    // Rotate if we're at or above the size threshold.
    if (currentFileBytes() >= maxFileBytes) {
      rotate();
    }

    appendLine(logPath, line);
  }

  /**
   * Flush any buffered state (no-op for sync implementation, kept for API symmetry).
   * Call on graceful shutdown.
   */
  function flush() {
    if (_pendingFlush) {
      clearTimeout(_pendingFlush);
      _pendingFlush = null;
    }
    // All writes are synchronous; nothing to flush.
  }

  /**
   * Return the current chain head hash (useful for integrity verification tests).
   */
  function getChainHead() {
    return prevHash;
  }

  /**
   * Verify the integrity hash chain of an existing log file.
   * Returns { ok, verified, firstBadLine }.
   *
   * @param {string} [filePath] — defaults to logPath
   * @returns {{ ok: boolean, verified: number, firstBadLine: number|null }}
   */
  function verifyChain(filePath) {
    const target = filePath || logPath;
    let lines;
    try {
      lines = fs.readFileSync(target, 'utf8').split('\n').filter(Boolean);
    } catch {
      return { ok: true, verified: 0, firstBadLine: null };
    }
    let runningHash = '0'.repeat(64);
    for (let i = 0; i < lines.length; i++) {
      let parsed;
      try {
        parsed = JSON.parse(lines[i]);
      } catch {
        return { ok: false, verified: i, firstBadLine: i + 1 };
      }
      const { integrity_hash: storedHash, ...rest } = parsed;
      const entryJson = JSON.stringify(rest);
      const expected = sha256(runningHash + entryJson);
      if (storedHash !== expected) {
        return { ok: false, verified: i, firstBadLine: i + 1 };
      }
      runningHash = storedHash;
    }
    return { ok: true, verified: lines.length, firstBadLine: null };
  }

  return { logAction, flush, getChainHead, verifyChain, logPath, archiveDir };
}

const actionAuditLog = createActionAuditLog();

export { createActionAuditLog, actionAuditLog };
