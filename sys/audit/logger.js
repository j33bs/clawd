'use strict';

const fs = require('node:fs');
const path = require('node:path');

const { computeEventHash, validateEventShape } = require('./schema');
const { redactValue } = require('./redaction');
const { isAuditEnabled, resolveAuditLogPath } = require('./policy');

function ensureParentDir(filePath) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
}

function appendAuditEvent(event, options = {}) {
  const env = options.env || process.env;
  const enabled = options.enabled !== undefined ? options.enabled : isAuditEnabled(env);
  if (!enabled) {
    return { written: false, reason: 'audit logging disabled' };
  }

  const logPath = options.logPath || resolveAuditLogPath(env);
  const normalized = redactValue({ ...event });
  normalized.hash = computeEventHash(normalized);

  const validation = validateEventShape(normalized);
  if (!validation.ok) {
    return {
      written: false,
      reason: `invalid event: ${validation.errors.join('; ')}`
    };
  }

  ensureParentDir(logPath);
  fs.appendFileSync(logPath, `${JSON.stringify(normalized)}\n`, 'utf8');
  return { written: true, logPath, event: normalized };
}

module.exports = {
  appendAuditEvent
};
