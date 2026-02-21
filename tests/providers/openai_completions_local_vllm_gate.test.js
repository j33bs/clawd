'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  applyLocalVllmToolPayloadGate,
  applyLocalVllmTokenGuard
} = require('../../core/system2/inference/openai_completions_local_vllm_gate');

test('strips tools and tool_choice for local vLLM when disabled', () => {
  const payload = {
    model: 'local-assistant',
    messages: [{ role: 'user', content: 'hi' }],
    tools: [{ type: 'function', function: { name: 'ping', parameters: { type: 'object' } } }],
    tool_choice: 'auto'
  };
  const out = applyLocalVllmToolPayloadGate('http://127.0.0.1:8001/v1', payload, { OPENCLAW_VLLM_TOOLCALL: '0' });
  assert.ok(!Object.prototype.hasOwnProperty.call(out, 'tools'));
  assert.ok(!Object.prototype.hasOwnProperty.call(out, 'tool_choice'));
  assert.ok(Object.prototype.hasOwnProperty.call(payload, 'tools'));
});

test('retains tools for local vLLM when explicitly enabled', () => {
  const payload = {
    model: 'local-assistant',
    messages: [{ role: 'user', content: 'hi' }],
    tools: [{ type: 'function', function: { name: 'ping', parameters: { type: 'object' } } }]
  };
  const out = applyLocalVllmToolPayloadGate('http://127.0.0.1:8001/v1', payload, { OPENCLAW_VLLM_TOOLCALL: '1' });
  assert.ok(Object.prototype.hasOwnProperty.call(out, 'tools'));
  assert.equal(out.tools.length, 1);
});

test('retains tools for non-local base URL regardless of toggle', () => {
  const payload = {
    model: 'gpt',
    messages: [{ role: 'user', content: 'hi' }],
    tools: [{ type: 'function', function: { name: 'ping', parameters: { type: 'object' } } }],
    tool_choice: 'auto'
  };
  const out = applyLocalVllmToolPayloadGate('https://api.openai.com/v1', payload, { OPENCLAW_VLLM_TOOLCALL: '0' });
  assert.ok(Object.prototype.hasOwnProperty.call(out, 'tools'));
  assert.ok(Object.prototype.hasOwnProperty.call(out, 'tool_choice'));
});

test('rejects oversized local vLLM request with structured token-budget error', () => {
  const payload = {
    model: 'local-assistant',
    messages: [{ role: 'user', content: 'x'.repeat(8000) }],
    max_completion_tokens: 4000
  };
  assert.throws(
    () =>
      applyLocalVllmTokenGuard('http://127.0.0.1:8001/v1', payload, {
        OPENCLAW_VLLM_TOKEN_GUARD: '1',
        OPENCLAW_VLLM_CONTEXT_MAX_TOKENS: '2048',
        OPENCLAW_VLLM_TOKEN_GUARD_MODE: 'reject'
      }),
    (err) =>
      err &&
      err.code === 'VLLM_CONTEXT_BUDGET_EXCEEDED' &&
      typeof err.prompt_est === 'number' &&
      err.context_max === 2048
  );
});

test('truncate mode shrinks messages and keeps dispatchable payload', () => {
  const payload = {
    model: 'local-assistant',
    messages: [
      { role: 'system', content: 'You are concise.' },
      { role: 'user', content: 'A'.repeat(4000) },
      { role: 'assistant', content: 'B'.repeat(4000) },
      { role: 'user', content: 'C'.repeat(3000) }
    ],
    max_completion_tokens: 16000
  };
  const result = applyLocalVllmTokenGuard('http://127.0.0.1:8001/v1', payload, {
    OPENCLAW_VLLM_TOKEN_GUARD: '1',
    OPENCLAW_VLLM_CONTEXT_MAX_TOKENS: '4096',
    OPENCLAW_VLLM_TOKEN_GUARD_MODE: 'truncate'
  });
  assert.ok(result && result.payload);
  assert.equal(result.diagnostic.action, 'truncate');
  assert.ok(Array.isArray(result.payload.messages));
  assert.ok(result.payload.messages.length < payload.messages.length);
  assert.ok(result.payload.max_completion_tokens <= 3840);
});
