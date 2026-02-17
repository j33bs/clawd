#!/usr/bin/env node
'use strict';

const assert = require('node:assert');

const { createVllmProvider, probeVllmServer } = require('../core/system2/inference/vllm_provider');
const { getProvider } = require('../core/system2/inference/catalog');

const LOCAL_VLLM_ENTRY = getProvider('local_vllm');

function test(name, fn) {
  tests.push({ name, fn });
}

const tests = [];

test('createVllmProvider ignores SYSTEM2_VLLM_* when system2 is false', async function () {
  assert.ok(LOCAL_VLLM_ENTRY, 'local_vllm should exist');

  const envBase = {
    OPENCLAW_VLLM_BASE_URL: 'http://system1.example.invalid/v1'
  };

  const envA = {
    ...envBase,
    SYSTEM2_VLLM_BASE_URL: 'http://system2-a.example.invalid/v1',
    SYSTEM2_VLLM_MODEL: 'system2-model-a',
    SYSTEM2_VLLM_TIMEOUT_MS: '11111'
  };

  const envB = {
    ...envBase,
    SYSTEM2_VLLM_BASE_URL: 'http://system2-b.example.invalid/v1',
    SYSTEM2_VLLM_MODEL: 'system2-model-b',
    SYSTEM2_VLLM_TIMEOUT_MS: '22222'
  };

  const pA = createVllmProvider({ env: envA, system2: false });
  const pB = createVllmProvider({ env: envB, system2: false });

  assert.strictEqual(pA.baseUrl, envBase.OPENCLAW_VLLM_BASE_URL);
  assert.strictEqual(pB.baseUrl, envBase.OPENCLAW_VLLM_BASE_URL);
  assert.notStrictEqual(pA.baseUrl, envA.SYSTEM2_VLLM_BASE_URL);
  assert.notStrictEqual(pB.baseUrl, envB.SYSTEM2_VLLM_BASE_URL);
});

test('probeVllmServer ignores SYSTEM2_VLLM_* when system2 is false', async function () {
  assert.ok(LOCAL_VLLM_ENTRY, 'local_vllm should exist');

  const envBase = {
    OPENCLAW_VLLM_BASE_URL: 'http://system1.example.invalid/v1'
  };

  const envA = {
    ...envBase,
    SYSTEM2_VLLM_BASE_URL: 'http://system2-a.example.invalid/v1',
    SYSTEM2_VLLM_MODEL: 'system2-model-a',
    SYSTEM2_VLLM_TIMEOUT_MS: '11111'
  };

  const envB = {
    ...envBase,
    SYSTEM2_VLLM_BASE_URL: 'http://system2-b.example.invalid/v1',
    SYSTEM2_VLLM_MODEL: 'system2-model-b',
    SYSTEM2_VLLM_TIMEOUT_MS: '22222'
  };

  function makeCapturingFactory(captured) {
    return function providerFactory(entry, derivedOptions) {
      captured.push({
        baseUrl: derivedOptions.baseUrl || null,
        openclaw_base_url: derivedOptions.env && derivedOptions.env.OPENCLAW_VLLM_BASE_URL || null,
        openclaw_model: derivedOptions.env && derivedOptions.env.OPENCLAW_VLLM_MODEL || null,
        system2: derivedOptions.system2 === true
      });

      return {
        health: async () => ({ ok: true, models: ['mock-model'] }),
        call: async () => ({ text: 'OK', usage: { inputTokens: 0, outputTokens: 0, totalTokens: 0, estimatedCostUsd: 0 } })
      };
    };
  }

  const capturedA = [];
  const resA = await probeVllmServer(
    LOCAL_VLLM_ENTRY,
    { env: envA, system2: false },
    { providerFactory: makeCapturingFactory(capturedA) }
  );

  const capturedB = [];
  const resB = await probeVllmServer(
    LOCAL_VLLM_ENTRY,
    { env: envB, system2: false },
    { providerFactory: makeCapturingFactory(capturedB) }
  );

  assert.strictEqual(capturedA.length, 1);
  assert.strictEqual(capturedB.length, 1);
  assert.deepStrictEqual(capturedA[0], capturedB[0]);
  assert.strictEqual(resA.base_url, envBase.OPENCLAW_VLLM_BASE_URL);
  assert.strictEqual(resB.base_url, envBase.OPENCLAW_VLLM_BASE_URL);
});

test('probeVllmServer consults SYSTEM2_VLLM_* when system2 is true', async function () {
  assert.ok(LOCAL_VLLM_ENTRY, 'local_vllm should exist');

  const env = {
    OPENCLAW_VLLM_BASE_URL: 'http://system1.example.invalid/v1',
    SYSTEM2_VLLM_BASE_URL: 'http://system2.example.invalid/v1'
  };

  const captured = [];
  const res = await probeVllmServer(
    LOCAL_VLLM_ENTRY,
    { env, system2: true },
    {
      providerFactory(entry, derivedOptions) {
        captured.push({
          openclaw_base_url: derivedOptions.env && derivedOptions.env.OPENCLAW_VLLM_BASE_URL || null,
          system2: derivedOptions.system2 === true
        });
        return {
          health: async () => ({ ok: true, models: ['mock-model'] }),
          call: async () => ({ text: 'OK', usage: { inputTokens: 0, outputTokens: 0, totalTokens: 0, estimatedCostUsd: 0 } })
        };
      }
    }
  );

  assert.strictEqual(captured.length, 1);
  assert.strictEqual(captured[0].system2, true);
  assert.strictEqual(captured[0].openclaw_base_url, env.SYSTEM2_VLLM_BASE_URL);
  assert.strictEqual(res.base_url, env.SYSTEM2_VLLM_BASE_URL);
});

test('probeVllmServer consults SYSTEM2_VLLM_* when nodeId alias resolves to c_lawd', async function () {
  assert.ok(LOCAL_VLLM_ENTRY, 'local_vllm should exist');
  const env = {
    OPENCLAW_VLLM_BASE_URL: 'http://system1.example.invalid/v1',
    SYSTEM2_VLLM_BASE_URL: 'http://system2.example.invalid/v1'
  };

  const captured = [];
  const res = await probeVllmServer(
    LOCAL_VLLM_ENTRY,
    { env, nodeId: 'system2' },
    {
      providerFactory(entry, derivedOptions) {
        captured.push({
          openclaw_base_url: derivedOptions.env && derivedOptions.env.OPENCLAW_VLLM_BASE_URL || null
        });
        return {
          baseUrl: 'unused',
          async health() { return { ok: true, models: ['m'] }; },
          async call() { return { text: 'OK' }; }
        };
      }
    }
  );

  assert.strictEqual(captured[0].openclaw_base_url, env.SYSTEM2_VLLM_BASE_URL);
  assert.strictEqual(res.base_url, env.SYSTEM2_VLLM_BASE_URL);
});

async function run() {
  for (const t of tests) {
    try {
      await t.fn();
      console.log('PASS ' + t.name);
    } catch (err) {
      console.error('FAIL ' + t.name + ': ' + err.message);
      process.exitCode = 1;
    }
  }
}

run();
