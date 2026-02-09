'use strict';

const fs = require('node:fs');
const path = require('node:path');

function run(context = {}) {
  const logDir = context.logDir || path.join(process.cwd(), 'logs');
  const logFile = path.join(logDir, 'sys_maintenance.jsonl');
  const record = {
    ts: new Date().toISOString(),
    event: context.event || 'maintenance_check',
    subsystem: context.subsystem || 'system-evolution'
  };

  fs.mkdirSync(logDir, { recursive: true });
  fs.appendFileSync(logFile, `${JSON.stringify(record)}\n`, 'utf8');

  return {
    name: 'unified_logging',
    logFile,
    wrote: true
  };
}

module.exports = { run };
