#!/usr/bin/env node
'use strict';

const assert = require('node:assert');

const { ProviderAdapter } = require('../../core/system2/inference/provider_adapter');

const tests = [];
function test(name, fn) {
  tests.push({ name, fn });
}

test('ProviderAdapter _httpPost strips tool_choice when tools are absent', async function () {
  const entry = {
    provider_id: 'provider_x',
    protocol: 'openai_compatible',
    base_url: { default: 'http://localhost:8000/v1', env_override: 'TEST_BASE_URL' },
    auth: { type: 'none', env_var: '' },
    models: [{ model_id: 'model-a', task_classes: ['fast_chat'], context_window_hint: 8192, tool_support: 'via_adapter', notes: '' }],
    healthcheck: { type: 'openai_compatible', endpoints: { models: '/models', chat: '/chat/completions' }, timeouts_ms: { read: 1000 } }
  };
  const adapter = new ProviderAdapter(entry, { env: {} });

  let seenBody = null;
  adapter._httpRequest = async function (_method, _url, body) {
    seenBody = body;
    return { ok: true };
  };

  await adapter._httpPost('http://localhost:8000/v1/chat/completions', {
    model: 'model-a',
    messages: [{ role: 'user', content: 'hi' }],
    tool_choice: 'auto'
  });

  assert.ok(seenBody, 'expected outbound request body');
  assert.ok(!Object.prototype.hasOwnProperty.call(seenBody, 'tool_choice'));
});

test('ProviderAdapter _httpPost strips tools/tool_choice when model does not support tool calls', async function () {
  const entry = {
    provider_id: 'provider_y',
    protocol: 'openai_compatible',
    base_url: { default: 'http://localhost:8000/v1', env_override: 'TEST_BASE_URL' },
    auth: { type: 'none', env_var: '' },
    models: [{ model_id: 'model-b', task_classes: ['fast_chat'], context_window_hint: 8192, tool_support: 'none', notes: '' }],
    healthcheck: { type: 'openai_compatible', endpoints: { models: '/models', chat: '/chat/completions' }, timeouts_ms: { read: 1000 } }
  };
  const adapter = new ProviderAdapter(entry, { env: {} });

  let seenBody = null;
  adapter._httpRequest = async function (_method, _url, body) {
    seenBody = body;
    return { ok: true };
  };

  await adapter._httpPost('http://localhost:8000/v1/chat/completions', {
    model: 'model-b',
    messages: [{ role: 'user', content: 'hi' }],
    tools: [{ type: 'function', function: { name: 'sum', parameters: { type: 'object' } } }],
    tool_choice: 'auto'
  });

  assert.ok(seenBody, 'expected outbound request body');
  assert.ok(!Object.prototype.hasOwnProperty.call(seenBody, 'tools'));
  assert.ok(!Object.prototype.hasOwnProperty.call(seenBody, 'tool_choice'));
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
