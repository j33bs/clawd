#!/usr/bin/env node
'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { buildSafeSpawnPlan, INLINE_MAX_BYTES } = require('../core/system2/safe_spawn');

function run(name, fn) {
  try {
    fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}: ${error.message}`);
    process.exitCode = 1;
  }
}

run('large payload uses tempfile transport and does not leak into argv/env', () => {
  const large = 'A'.repeat(200 * 1024);
  const plan = buildSafeSpawnPlan(
    '/bin/echo',
    ['ok'],
    { env: { SAFE_SPAWN_TEST: '1' } },
    { chat: { history: large } }
  );

  assert.equal(plan.mode, 'file');
  assert.ok(plan.payloadFile);
  assert.ok(fs.existsSync(plan.payloadFile));
  assert.ok(plan.args.includes('--payload-file'));
  assert.equal(plan.payloadText, null);
  assert.ok(!plan.args.join(' ').includes(large.slice(0, 128)));
  assert.equal(plan.options.env.SAFE_SPAWN_TEST, '1');
  assert.ok(!Object.values(plan.options.env).some((v) => String(v).includes(large.slice(0, 128))));

  const payloadFileContent = fs.readFileSync(plan.payloadFile, 'utf8');
  assert.ok(payloadFileContent.length > INLINE_MAX_BYTES);
  assert.match(payloadFileContent, /"history":/);
});

run('small payload uses stdin transport', () => {
  const small = { message: 'hello', count: 2 };
  const plan = buildSafeSpawnPlan('/bin/cat', [], {}, small);

  assert.equal(plan.mode, 'stdin');
  assert.equal(plan.payloadFile, null);
  assert.equal(typeof plan.payloadText, 'string');
  assert.ok(plan.payloadText.includes('"message":"hello"'));
  assert.deepEqual(plan.args, []);
});

run('empty payload uses none transport', () => {
  const plan = buildSafeSpawnPlan('/bin/echo', ['ok'], {}, null);

  assert.equal(plan.mode, 'none');
  assert.equal(plan.payloadFile, null);
  assert.equal(plan.payloadText, null);
  assert.deepEqual(plan.args, ['ok']);
});

console.log(`safe_spawn tests complete (${path.basename(__filename)})`);
