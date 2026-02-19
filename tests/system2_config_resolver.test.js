#!/usr/bin/env node
'use strict';

const assert = require('node:assert');

const { resolveSystem2VllmConfig } = require('../core/system2/inference/system2_config_resolver');

function test(name, fn) {
  try {
    fn();
    console.log('PASS ' + name);
  } catch (err) {
    console.error('FAIL ' + name + ': ' + err.message);
    process.exitCode = 1;
  }
}

test('resolves with explicit args (highest precedence)', function () {
  const config = resolveSystem2VllmConfig({
    baseUrl: 'http://custom:9999/v1',
    apiKey: 'explicit-key',
    env: {}
  });
  assert.strictEqual(config.base_url, 'http://custom:9999/v1');
  assert.strictEqual(config.api_key, 'explicit-key');
});

test('falls back to SYSTEM2_VLLM_* env vars', function () {
  const config = resolveSystem2VllmConfig({
    env: {
      SYSTEM2_VLLM_BASE_URL: 'http://system2:8888/v1',
      SYSTEM2_VLLM_API_KEY: 'system2-key'
    }
  });
  assert.strictEqual(config.base_url, 'http://system2:8888/v1');
  assert.strictEqual(config.api_key, 'system2-key');
});

test('falls back to OPENCLAW_VLLM_* env vars', function () {
  const config = resolveSystem2VllmConfig({
    env: {
      OPENCLAW_VLLM_BASE_URL: 'http://system1:7777/v1',
      OPENCLAW_VLLM_API_KEY: 'system1-key'
    }
  });
  assert.strictEqual(config.base_url, 'http://system1:7777/v1');
  assert.strictEqual(config.api_key, 'system1-key');
});

test('prefers SYSTEM2_VLLM_* over OPENCLAW_VLLM_*', function () {
  const config = resolveSystem2VllmConfig({
    env: {
      SYSTEM2_VLLM_BASE_URL: 'http://system2:8888/v1',
      OPENCLAW_VLLM_BASE_URL: 'http://system1:7777/v1',
      OPENCLAW_VLLM_API_KEY: 'system1-key'
    }
  });
  assert.strictEqual(config.base_url, 'http://system2:8888/v1');
  assert.strictEqual(config.api_key, 'system1-key');
});

test('uses node alias system-2 for c_lawd routing context', function () {
  const config = resolveSystem2VllmConfig({
    nodeId: 'system-2',
    env: {
      SYSTEM2_VLLM_BASE_URL: 'http://system2:8888/v1',
      OPENCLAW_VLLM_BASE_URL: 'http://system1:7777/v1'
    }
  });
  assert.strictEqual(config.base_url, 'http://system2:8888/v1');
});

test('uses defaults when envs not set', function () {
  const config = resolveSystem2VllmConfig({ env: {} });
  assert.strictEqual(config.base_url, 'http://127.0.0.1:8000/v1');
  assert.strictEqual(config.api_key, null);
  assert.strictEqual(config.timeout_ms, 30000);
});

test('emits diagnostic events (keys only)', function () {
  const events = [];
  const emit = (type, payload) => events.push({ type, payload });
  resolveSystem2VllmConfig({
    env: { OPENCLAW_VLLM_BASE_URL: 'http://test:7777/v1' },
    emitEvent: emit
  });
  assert.strictEqual(events.length, 1);
  assert.strictEqual(events[0].type, 'system2_vllm_config_resolved');
  assert.ok(events[0].payload.keys);
  assert.strictEqual(typeof events[0].payload.base_url_source, 'string');
});

test('resolves numeric config deterministically', function () {
  const config = resolveSystem2VllmConfig({
    env: {
      SYSTEM2_VLLM_TIMEOUT_MS: '45000',
      SYSTEM2_VLLM_MAX_CONCURRENCY: '8'
    }
  });
  assert.strictEqual(config.timeout_ms, 45000);
  assert.strictEqual(config.max_concurrent_requests, 8);
  assert.strictEqual(typeof config.timeout_ms, 'number');
});

test('invalid numeric env yields NaN (no throw)', function () {
  const config = resolveSystem2VllmConfig({
    env: {
      SYSTEM2_VLLM_TIMEOUT_MS: 'not_a_number'
    }
  });
  assert.ok(Number.isNaN(config.timeout_ms));
});
