'use strict';

const assert = require('node:assert/strict');
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

run('fast ack returns immediate 200 with deferred=false for small payload', () => {
  const ack = mod.fastAck({ message: { text: 'hi' } }, { corrId: 'corr_fast_ack' });
  assert.equal(ack.statusCode, 200);
  assert.equal(ack.body.ok, true);
  assert.equal(ack.body.corr_id, 'corr_fast_ack');
  assert.equal(ack.body.deferred, false);
  assert.equal(ack.body.defer_reason, 'inline_ok');
  const text = JSON.stringify(ack.body);
  assert.ok(!text.includes('prompt'));
  assert.ok(!text.includes('document_body'));
});

console.log('telegram_fast_ack tests complete');
