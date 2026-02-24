#!/usr/bin/env node
'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');

const { writeTelegramDeadletter } = require('../workspace/scripts/telegram_hardening_helpers');

function run(name, fn) {
  Promise.resolve()
    .then(fn)
    .then(() => console.log(`PASS ${name}`))
    .catch((error) => {
      console.error(`FAIL ${name}: ${error.message}`);
      process.exitCode = 1;
    });
}

run('deadletter writer creates directory and file', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'openclaw-deadletter-test-'));
  const payload = { update_id: 533, route: 'telegram_inbound', error: 'simulated' };
  const out = await writeTelegramDeadletter({ dir, basename: 'tg', payload });
  assert.equal(out.ok, true);
  assert.equal(fs.existsSync(out.path), true);
  const body = fs.readFileSync(out.path, 'utf8');
  const parsed = JSON.parse(body);
  assert.equal(parsed.update_id, 533);
  assert.equal(parsed.route, 'telegram_inbound');
});
