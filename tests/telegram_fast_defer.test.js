#!/usr/bin/env node
'use strict';

const assert = require('node:assert/strict');

const {
  createFastAckTelegramHandler,
  shouldDeferTelegramUpdate
} = require('../workspace/scripts/telegram_hardening_helpers');

function run(name, fn) {
  Promise.resolve()
    .then(fn)
    .then(() => console.log(`PASS ${name}`))
    .catch((error) => {
      console.error(`FAIL ${name}: ${error.message}`);
      process.exitCode = 1;
    });
}

run('heuristic defers arxiv updates', () => {
  const msg = { text: 'check https://arxiv.org/abs/2501.00001' };
  assert.equal(shouldDeferTelegramUpdate(msg), true);
});

run('handler defers heavy updates and returns quickly', async () => {
  let heavyCalls = 0;
  const queued = [];
  const handler = createFastAckTelegramHandler({
    processInbound: async () => {
      heavyCalls += 1;
      await new Promise((resolve) => setTimeout(resolve, 30));
    },
    enqueue: (fn) => {
      queued.push(fn);
    }
  });

  const result = await handler({ msg: { text: 'https://arxiv.org/abs/2501.00001' } });
  assert.equal(result.deferred, true);
  assert.equal(heavyCalls, 0);
  assert.equal(queued.length, 1);
  assert.ok(result.elapsed_ms < 1000);

  await queued[0]();
  assert.equal(heavyCalls, 1);
});
