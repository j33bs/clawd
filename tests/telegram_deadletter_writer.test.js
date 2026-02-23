'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const mod = require(path.join(__dirname, '..', 'scripts', 'system2', 'telegram_reliability.js'));

function run(name, fn) {
  try {
    fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}: ${error.message}`);
    process.exitCode = 1;
  }
}

run('deadletter writer stores metadata only and stable envelope fields', () => {
  const target = path.join(os.tmpdir(), `telegram_deadletter_${Date.now()}_${Math.random()}.jsonl`);
  const out = mod.writeDeadletter(
    {
      corr_id: 'corr_deadletter',
      reason: 'timeout',
      prompt: 'must_be_removed',
      text: 'must_be_removed',
      details: { text: 'must_be_removed_nested', keep: 'ok' }
    },
    { OPENCLAW_TELEGRAM_DEADLETTER_PATH: target }
  );
  assert.equal(out.ok, true);
  const lines = fs.readFileSync(target, 'utf8').trim().split(/\r?\n/);
  assert.equal(lines.length, 1);
  const obj = JSON.parse(lines[0]);
  assert.equal(obj.corr_id, 'corr_deadletter');
  assert.equal(obj.reason, 'timeout');
  assert.equal(obj.redaction_mode, 'metadata_only');
  const asText = JSON.stringify(obj);
  assert.ok(!asText.includes('must_be_removed'));
  assert.ok(asText.includes('"keep":"ok"'));
});

console.log('telegram_deadletter_writer tests complete');
