import test from 'node:test';
import assert from 'node:assert/strict';

import {
  CHANNEL_TEXT_LIMITS,
  SAFE_EMPTY_FALLBACK,
  ensureNonEmptyOutbound,
  sanitizeOutboundPayload,
  sanitizeOutboundText
} from '../src/outbound_sanitize.mjs';

test('outbound sanitizer strips internal reasoning section', () => {
  const input = 'Hello\n\nReasoning:\n<internal details>';
  const { text } = sanitizeOutboundText(input, { channel: 'discord' });
  assert.equal(text, 'Hello');
  assert.equal(text.includes('Reasoning:'), false);
});

test('ensureNonEmptyOutbound replaces empty and legacy sentinel text', () => {
  assert.equal(ensureNonEmptyOutbound('   ', SAFE_EMPTY_FALLBACK), SAFE_EMPTY_FALLBACK);
  assert.equal(
    ensureNonEmptyOutbound('No response generated. Please try again.', SAFE_EMPTY_FALLBACK),
    SAFE_EMPTY_FALLBACK
  );
});

test('outbound sanitizer strips analysis tag blocks', () => {
  const input = 'Hello\n<analysis>internal</analysis>\nworld';
  const { text } = sanitizeOutboundText(input, { channel: 'teamchat' });
  assert.equal(text, 'Hello\n\nworld');
});

test('outbound sanitizer truncates by channel limit', () => {
  const input = 'x'.repeat(CHANNEL_TEXT_LIMITS.discord + 40);
  const { text, meta } = sanitizeOutboundText(input, { channel: 'discord' });
  assert.equal(text.length, CHANNEL_TEXT_LIMITS.discord);
  assert.equal(meta.truncated, true);
  assert.equal(text.endsWith('…'), true);
});

test('sanitizeOutboundPayload applies fallback for teamchat gateway payload', () => {
  const sanitized = sanitizeOutboundPayload(
    {
      channel: 'teamchat',
      message: 'No response generated. Please try again.'
    },
    { channel: 'teamchat' }
  );

  assert.equal(sanitized.payload.message, SAFE_EMPTY_FALLBACK);
  assert.equal(sanitized.meta.reason, 'EMPTY_OR_STRIPPED');
});
