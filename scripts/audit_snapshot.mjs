#!/usr/bin/env node
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { appendAuditEvent } = require('../sys/audit/logger');
const { buildSnapshotEvent } = require('../sys/audit/snapshot');
const { formatOperatorSummary, isAuditEnabled, resolveAuditLogPath } = require('../sys/audit/policy');

const enabled = isAuditEnabled(process.env);
if (!enabled) {
  console.log(formatOperatorSummary({
    changed: 'none',
    verified: ['preflight'],
    blocked: 'OPENCLAW_AUDIT_LOGGING is not enabled',
    nextAction: 'OPENCLAW_AUDIT_LOGGING=1 node scripts/audit_snapshot.mjs'
  }));
  process.exit(1);
}

const event = buildSnapshotEvent({ projectRoot: process.cwd(), env: process.env });
const writeResult = appendAuditEvent(event, { env: process.env, enabled: true });

if (!writeResult.written) {
  console.log(formatOperatorSummary({
    changed: 'none',
    verified: ['snapshot'],
    blocked: writeResult.reason,
    nextAction: 'node scripts/audit_verify.mjs'
  }));
  process.exit(1);
}

console.log(formatOperatorSummary({
  changed: `audit_event_written:${resolveAuditLogPath(process.env)}`,
  verified: ['snapshot_schema', 'snapshot_hash'],
  blocked: 'none',
  nextAction: 'node scripts/audit_verify.mjs'
}));
