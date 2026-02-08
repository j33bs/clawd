'use strict';

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

function ensureDir(p) {
  fs.mkdirSync(p, { recursive: true });
}

function hash(str) {
  return crypto.createHash('sha256').update(str || '').digest('hex');
}

function appendAudit(entry) {
  const dir = path.join(process.cwd(), 'logs');
  ensureDir(dir);
  const file = path.join(dir, 'prompt_audit.jsonl');
  fs.appendFileSync(file, `${JSON.stringify(entry)}\n`, 'utf8');
}

module.exports = { appendAudit, hash };
