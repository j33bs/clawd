#!/usr/bin/env node
'use strict';

const assert = require('node:assert');

const { LocalVllmProvider, normalizeBaseUrl } = require('../../core/system2/inference/local_vllm_provider');

const tests = [];
function test(name, fn) {
  tests.push({ name, fn });
}

test('healthProbe succeeds against mocked vLLM endpoint and normalizes /v1', async function () {
  const provider = new LocalVllmProvider({
    env: { OPENCLAW_VLLM_BASE_URL: 'http://localhost:18888' }
  });
  let seenUrl = null;
  provider._httpRequest = async function (_method, url) {
    seenUrl = url;
    return { data: [{ id: 'qwen2.5' }] };
  };
  const result = await provider.healthProbe();
  assert.strictEqual(result.ok, true);
  assert.deepStrictEqual(result.models, ['qwen2.5']);
  assert.strictEqual(seenUrl, 'http://localhost:18888/v1/models');
});

test('healthProbe returns fail-closed result when endpoint is unreachable', async function () {
  const provider = new LocalVllmProvider({
    env: { OPENCLAW_VLLM_BASE_URL: 'http://localhost:18888' }
  });
  provider._httpRequest = async function () {
    throw new Error('timeout connecting to local_vllm');
  };
  const result = await provider.health();
  assert.strictEqual(result.ok, false);
  assert.strictEqual(typeof result.reason, 'string');
  assert.strictEqual(result.reason, 'timeout connecting to local_vllm');
});

test('generateChat returns expected output shape from vLLM response', async function () {
  const provider = new LocalVllmProvider({
    env: { OPENCLAW_VLLM_BASE_URL: 'http://localhost:18888' }
  });
  let seenUrl = null;
  provider._httpRequest = async function (_method, url) {
    seenUrl = url;
    return {
      model: 'qwen2.5',
      choices: [{ message: { content: 'hello from vllm' } }],
      usage: { prompt_tokens: 3, completion_tokens: 4, total_tokens: 7 }
    };
  };

  const output = await provider.generateChat({
    messages: [{ role: 'user', content: 'hi' }],
    options: { model: 'qwen2.5', maxTokens: 16 }
  });

  assert.strictEqual(seenUrl, 'http://localhost:18888/v1/chat/completions');
  assert.strictEqual(output.text, 'hello from vllm');
  assert.strictEqual(output.model, 'qwen2.5');
  assert.strictEqual(output.usage.inputTokens, 3);
  assert.strictEqual(output.usage.outputTokens, 4);
  assert.strictEqual(output.usage.totalTokens, 7);
  assert.ok(output.raw);
});

test('generateChat strips tool payload fields by default', async function () {
  const provider = new LocalVllmProvider({
    env: { OPENCLAW_VLLM_BASE_URL: 'http://localhost:18888' }
  });
  let seenBody = null;
  provider._httpRequest = async function (_method, _url, body) {
    seenBody = body;
    return {
      model: 'qwen2.5',
      choices: [{ message: { content: 'ok' } }],
      usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 }
    };
  };

  await provider.generateChat({
    messages: [{ role: 'user', content: 'hi' }],
    options: {
      model: 'qwen2.5',
      tools: [{ type: 'function', function: { name: 'sum', parameters: { type: 'object' } } }],
      tool_choice: 'auto',
      parallel_tool_calls: true,
      tool_calls: [{ id: 'call_1' }],
      function_call: { name: 'sum' }
    }
  });

  assert.ok(seenBody, 'expected request payload');
  assert.ok(!Object.prototype.hasOwnProperty.call(seenBody, 'tools'));
  assert.ok(!Object.prototype.hasOwnProperty.call(seenBody, 'tool_choice'));
  assert.ok(!Object.prototype.hasOwnProperty.call(seenBody, 'parallel_tool_calls'));
  assert.ok(!Object.prototype.hasOwnProperty.call(seenBody, 'tool_calls'));
  assert.ok(!Object.prototype.hasOwnProperty.call(seenBody, 'function_call'));
});

test('generateChat removes tool_choice when tools are absent', async function () {
  const provider = new LocalVllmProvider({
    env: {
      OPENCLAW_VLLM_BASE_URL: 'http://localhost:18888',
      OPENCLAW_VLLM_ENABLE_AUTO_TOOL_CHOICE: '1',
      OPENCLAW_VLLM_TOOLCALL: '1'
    }
  });
  let seenBody = null;
  provider._httpRequest = async function (_method, _url, body) {
    seenBody = body;
    return {
      model: 'qwen2.5',
      choices: [{ message: { content: 'ok' } }],
      usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 }
    };
  };

  await provider.generateChat({
    messages: [{ role: 'user', content: 'hi' }],
    options: {
      model: 'qwen2.5',
      tool_choice: 'auto'
    }
  });

  assert.ok(seenBody, 'expected request payload');
  assert.ok(!Object.prototype.hasOwnProperty.call(seenBody, 'tools'));
  assert.ok(!Object.prototype.hasOwnProperty.call(seenBody, 'tool_choice'));
});

test('normalizeBaseUrl appends /v1 only when missing', function () {
  assert.strictEqual(normalizeBaseUrl('http://localhost:18888'), 'http://localhost:18888/v1');
  assert.strictEqual(normalizeBaseUrl('http://localhost:18888/v1'), 'http://localhost:18888/v1');
  assert.strictEqual(normalizeBaseUrl('http://localhost:18888/'), 'http://localhost:18888/v1');
  assert.strictEqual(normalizeBaseUrl('http://localhost:18888/v1/'), 'http://localhost:18888/v1');
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
