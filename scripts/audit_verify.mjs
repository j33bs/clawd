#!/usr/bin/env node
import fs from 'node:fs';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { validateEventShape, computeEventHash } = require('../sys/audit/schema');
const { formatOperatorSummary, resolveAuditLogPath } = require('../sys/audit/policy');

const logPath = resolveAuditLogPath(process.env);
if (!fs.existsSync(logPath)) {
  console.log(formatOperatorSummary({
    changed: 'none',
    verified: [],
    blocked: `audit log missing at ${logPath}`,
    nextAction: 'OPENCLAW_AUDIT_LOGGING=1 node scripts/audit_snapshot.mjs'
  }));
  process.exit(1);
}

const lines = fs.readFileSync(logPath, 'utf8').split('\n').filter(Boolean);
if (lines.length === 0) {
  console.log(formatOperatorSummary({
    changed: 'none',
    verified: [],
    blocked: 'audit log is empty',
    nextAction: 'OPENCLAW_AUDIT_LOGGING=1 node scripts/audit_snapshot.mjs'
  }));
  process.exit(1);
}

for (const [index, line] of lines.entries()) {
  let event;
  try {
    event = JSON.parse(line);
  } catch (error) {
    console.log(formatOperatorSummary({
      changed: 'none',
      verified: [],
      blocked: `invalid JSON at line ${index + 1}: ${error.message}`,
      nextAction: 'inspect audit log line and regenerate snapshot'
    }));
    process.exit(1);
  }

  const validation = validateEventShape(event);
  if (!validation.ok) {
    console.log(formatOperatorSummary({
      changed: 'none',
      verified: [],
      blocked: `schema failure line ${index + 1}: ${validation.errors.join('; ')}`,
      nextAction: 'regenerate events with current schema'
    }));
    process.exit(1);
  }

  const hash = computeEventHash(event);
  if (hash !== event.hash) {
    console.log(formatOperatorSummary({
      changed: 'none',
      verified: [],
      blocked: `hash mismatch at line ${index + 1}`,
      nextAction: 'discard tampered line and regenerate snapshot'
    }));
    process.exit(1);
  }
}

console.log(formatOperatorSummary({
  changed: 'none',
  verified: ['schema', 'hash', `events:${lines.length}`],
  blocked: 'none',
  nextAction: 'create or validate change capsule'
}));
