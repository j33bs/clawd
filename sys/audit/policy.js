'use strict';

const os = require('node:os');
const path = require('node:path');

const EVENT_TYPES = [
  'audit.snapshot',
  'audit.run.start',
  'audit.run.end',
  'audit.change.detected',
  'audit.external.health',
  'audit.invariant.pass',
  'audit.invariant.fail',
  'audit.operator.notice'
];

function isAuditEnabled(env = process.env) {
  return String(env.OPENCLAW_AUDIT_LOGGING || '') === '1';
}

function resolveAuditLogPath(env = process.env) {
  return env.OPENCLAW_AUDIT_LOG_PATH || path.join(os.homedir(), '.openclaw', 'logs', 'audit.jsonl');
}

function shouldLogEvent(eventType, env = process.env) {
  return isAuditEnabled(env) && EVENT_TYPES.includes(eventType);
}

function formatOperatorSummary({ changed = 'none', verified = [], blocked = 'none', nextAction = 'none' }) {
  const lines = [];
  lines.push(`OPERATOR_SUMMARY changed=${changed}`);
  lines.push(`OPERATOR_SUMMARY verified=${verified.length ? verified.join(', ') : 'none'}`);
  lines.push(`OPERATOR_SUMMARY blocked=${blocked}`);
  lines.push(`OPERATOR_SUMMARY next_action=${nextAction}`);
  return lines.join('\n');
}

module.exports = {
  EVENT_TYPES,
  isAuditEnabled,
  resolveAuditLogPath,
  shouldLogEvent,
  formatOperatorSummary
};
