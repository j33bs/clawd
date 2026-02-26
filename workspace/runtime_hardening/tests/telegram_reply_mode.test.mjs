import test from 'node:test';
import assert from 'node:assert/strict';

import { buildTelegramSendPayload } from '../src/telegram_reply_mode.mjs';

test('TELEGRAM_REPLY_MODE=never removes Telegram reply threading fields', () => {
  const { payload, wantsReply } = buildTelegramSendPayload({
    mode: 'never',
    incomingText: '/status',
    payload: {
      chat_id: '100',
      text: 'ok',
      reply_to_message_id: 55,
      reply_parameters: { message_id: 55 }
    }
  });

  assert.equal(wantsReply, false);
  assert.equal(Object.hasOwn(payload, 'reply_to_message_id'), false);
  assert.equal(Object.hasOwn(payload, 'reply_parameters'), false);
});

test('TELEGRAM_REPLY_MODE=always preserves Telegram reply threading fields', () => {
  const { payload, wantsReply } = buildTelegramSendPayload({
    mode: 'always',
    payload: {
      chat_id: '100',
      text: 'ok',
      reply_parameters: { message_id: 55, quote: 'hello' },
      reply_to_message_id: 55
    }
  });

  assert.equal(wantsReply, true);
  assert.equal(Object.hasOwn(payload, 'reply_parameters'), true);
  assert.equal(Object.hasOwn(payload, 'reply_to_message_id'), false);
});

test('TELEGRAM_REPLY_MODE=auto replies for command-like input only', () => {
  const commandLike = buildTelegramSendPayload({
    mode: 'auto',
    incomingText: '/help',
    payload: {
      chat_id: '100',
      text: 'ok',
      reply_to_message_id: 55
    }
  });
  assert.equal(commandLike.wantsReply, true);
  assert.equal(Object.hasOwn(commandLike.payload, 'reply_to_message_id'), true);

  const normal = buildTelegramSendPayload({
    mode: 'auto',
    incomingText: 'what is the weather',
    payload: {
      chat_id: '100',
      text: 'ok',
      reply_to_message_id: 55
    }
  });
  assert.equal(normal.wantsReply, false);
  assert.equal(Object.hasOwn(normal.payload, 'reply_to_message_id'), false);
  assert.equal(Object.hasOwn(normal.payload, 'reply_parameters'), false);
});
