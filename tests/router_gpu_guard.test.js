#!/usr/bin/env node
'use strict';

const assert = require('node:assert/strict');
const { routeRequest } = require('../core/system2/inference/router');

function test(name, fn) {
  try {
    fn();
    console.log('PASS ' + name);
  } catch (err) {
    console.error('FAIL ' + name + ': ' + err.message);
    process.exitCode = 1;
  }
}

test('routeRequest removes local_vllm candidates when gpu guard deflects', () => {
  const out = routeRequest({
    taskClass: 'fast_chat',
    config: {
      enabled: true,
      vllmEnabled: true,
      tactiCrRoutingEnabled: false,
      providerAllowlist: [],
      providerDenylist: []
    },
    providerHealth: {},
    quotaState: {},
    availableProviderIds: ['local_vllm', 'minimax-portal'],
    gpuGuard: { shouldDeflect: () => true }
  });
  assert.ok(out.candidates.length > 0);
  assert.ok(!out.candidates.some((c) => c.provider_id === 'local_vllm'));
});
