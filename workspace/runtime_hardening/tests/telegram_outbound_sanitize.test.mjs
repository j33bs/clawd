import test from 'node:test';
import assert from 'node:assert/strict';

import {
  SAFE_EMPTY_FALLBACK,
  sanitizeOutboundText,
  sanitizeTelegramOutboundPayload
} from '../src/telegram_outbound_sanitize.mjs';

test('reasoning leak is stripped from outbound text', () => {
  const input = 'Hello\n\nReasoning:\n<stuff>';
  const out = sanitizeOutboundText(input);
  assert.equal(out, 'Hello');
  assert.equal(out.includes('Reasoning:'), false);
});

test('empty outbound response uses safe fallback', () => {
  const { payload, usedFallback } = sanitizeTelegramOutboundPayload({
    chat_id: '1',
    reply_to_message_id: '2',
    text: '   '
  });

  assert.equal(usedFallback, true);
  assert.equal(payload.text, SAFE_EMPTY_FALLBACK);
  assert.equal(payload.text.includes('No response generated. Please try again.'), false);
});

test('stripped-to-empty outbound response uses safe fallback', () => {
  const { payload, usedFallback } = sanitizeTelegramOutboundPayload({
    chat_id: '1',
    reply_to_message_id: '2',
    text: 'Reasoning:\nonly internal'
  });

  assert.equal(usedFallback, true);
  assert.equal(payload.text, SAFE_EMPTY_FALLBACK);
  assert.equal(payload.text.includes('Reasoning:'), false);
});
