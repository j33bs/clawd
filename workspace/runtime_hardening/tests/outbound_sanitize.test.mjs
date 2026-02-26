import test from 'node:test';
import assert from 'node:assert/strict';

import {
  SAFE_EMPTY_FALLBACK,
  ensureNonEmptyOutbound,
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
