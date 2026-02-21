'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  applyLocalVllmToolPayloadGate
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
