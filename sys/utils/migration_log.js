'use strict';

const fs = require('node:fs');
const path = require('node:path');

function appendMigrationLog(entry, options = {}) {
  const logPath =
    options.logPath ||
    path.join(process.cwd(), 'logs', 'system_evolution_2026-02-09.txt');

  const payload = {
    ts: new Date().toISOString(),
    ...(entry || {})
  };

  fs.mkdirSync(path.dirname(logPath), { recursive: true });
  fs.appendFileSync(logPath, `${JSON.stringify(payload)}\n`, 'utf8');
  return logPath;
}

module.exports = {
  appendMigrationLog
};
