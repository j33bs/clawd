#!/usr/bin/env node
'use strict';

const assert = require('node:assert');

const { sanitizeToolPayload, enforceToolPayloadInvariant } = require('../../core/system2/inference/tool_payload_sanitizer');

function test(name, fn) {
  try {
    fn();
    console.log('PASS ' + name);
  } catch (error) {
    console.error('FAIL ' + name + ': ' + error.message);
    process.exitCode = 1;
  }
}

test('removes tool_choice when tools are missing', function () {
  const input = { model: 'm', messages: [], tool_choice: 'auto' };
  const out = sanitizeToolPayload(input, { tool_calls_supported: true });
  assert.ok(!Object.prototype.hasOwnProperty.call(out, 'tool_choice'));
});

test('removes tools and tool_choice when tools are empty array', function () {
  const input = { model: 'm', messages: [], tools: [], tool_choice: 'auto' };
  const out = sanitizeToolPayload(input, { tool_calls_supported: true });
  assert.ok(!Object.prototype.hasOwnProperty.call(out, 'tools'));
  assert.ok(!Object.prototype.hasOwnProperty.call(out, 'tool_choice'));
});

test('removes tools and tool_choice when provider does not support tool calls', function () {
  const input = {
    model: 'm',
    messages: [],
    tools: [{ type: 'function', function: { name: 'sum', parameters: { type: 'object' } } }],
    tool_choice: 'auto'
  };
  const out = sanitizeToolPayload(input, { tool_calls_supported: false });
  assert.ok(!Object.prototype.hasOwnProperty.call(out, 'tools'));
  assert.ok(!Object.prototype.hasOwnProperty.call(out, 'tool_choice'));
});

test('strict mode raises structured bypass error for tool_choice without tools', function () {
  const prev = process.env.OPENCLAW_STRICT_TOOL_PAYLOAD;
  process.env.OPENCLAW_STRICT_TOOL_PAYLOAD = '1';
  try {
    assert.throws(
      () => enforceToolPayloadInvariant(
        { model: 'm', messages: [], tool_choice: 'auto' },
        { tool_calls_supported: true },
        { provider_id: 'p', model_id: 'm', callsite_tag: 'gateway.adapter.final_dispatch' }
      ),
      (err) => err && err.code === 'TOOL_PAYLOAD_SANITIZER_BYPASSED' && err.details && err.details.callsite_tag === 'gateway.adapter.final_dispatch'
    );
  } finally {
    if (prev === undefined) delete process.env.OPENCLAW_STRICT_TOOL_PAYLOAD;
    else process.env.OPENCLAW_STRICT_TOOL_PAYLOAD = prev;
  }
});
