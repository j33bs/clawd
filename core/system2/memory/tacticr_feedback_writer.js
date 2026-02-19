'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { sanitizeContextInput } = require('../context_sanitizer');
const { resolveRepoRoot } = require('../security/integrity_guard');

const DEFAULT_RELATIVE_PATH = 'workspace/memory/tacticr_feedback.jsonl';

function sanitizeNotes(input) {
  const sanitized = sanitizeContextInput(input || '').sanitizedText;
  return sanitized.replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, '').trim();
}

function normalizeEntry(entry) {
  if (!entry || typeof entry !== 'object') {
    throw new Error('entry must be an object');
  }
  if (!entry.decision_id || typeof entry.decision_id !== 'string') {
    throw new Error('decision_id is required');
  }
  if (!entry.outcome || typeof entry.outcome !== 'string') {
    throw new Error('outcome is required');
  }

  const refs = Array.isArray(entry.principle_refs)
    ? entry.principle_refs.map((x) => String(x)).filter(Boolean)
    : [];

  return {
    ts_utc: entry.ts_utc || new Date().toISOString(),
    decision_id: entry.decision_id,
    principle_refs: refs,
    outcome: entry.outcome,
    notes: sanitizeNotes(entry.notes || '')
  };
}

function appendFeedback(entry, opts = {}) {
  const repoRoot = resolveRepoRoot(opts.repoRoot || process.cwd());
  const relPath = opts.relativePath || DEFAULT_RELATIVE_PATH;
  const absPath = path.join(repoRoot, relPath);
  fs.mkdirSync(path.dirname(absPath), { recursive: true });

  const normalized = normalizeEntry(entry);
  const line = `${JSON.stringify(normalized)}\n`;

  const fd = fs.openSync(absPath, 'a');
  try {
    fs.writeFileSync(fd, line, 'utf8');
  } finally {
    fs.closeSync(fd);
  }

  return {
    path: absPath,
    entry: normalized
  };
}

module.exports = {
  DEFAULT_RELATIVE_PATH,
  appendFeedback,
  normalizeEntry,
  sanitizeNotes
};
