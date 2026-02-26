import {
  CHANNEL_TEXT_LIMITS,
  LEGACY_EMPTY_RESPONSE,
  SAFE_EMPTY_FALLBACK,
  sanitizeOutboundPayload,
  sanitizeOutboundText as sanitizeSharedOutboundText,
  truncateOutboundText
} from './outbound_sanitize.mjs';
import { buildTelegramSendPayload } from './telegram_reply_mode.mjs';

const TELEGRAM_TEXT_LIMIT = CHANNEL_TEXT_LIMITS.telegram;

function sanitizeOutboundText(text) {
  return sanitizeSharedOutboundText(text, { channel: 'telegram' }).text;
}

function sanitizeTelegramOutboundPayload(payload, options = {}) {
  const sanitized = sanitizeOutboundPayload(payload, {
    ...options,
    channel: 'telegram'
  });
  const replyAdjusted = buildTelegramSendPayload({
    payload: sanitized.payload,
    mode: options.telegramReplyMode ?? options.replyMode ?? 'never',
    incomingText: options.incomingText
  });
  const changed =
    sanitized.changed ||
    JSON.stringify(replyAdjusted.payload) !== JSON.stringify(sanitized.payload);

  return {
    payload: replyAdjusted.payload,
    changed,
    usedFallback: sanitized.usedFallback,
    correlationId: sanitized.meta.correlation_id,
    wantsReply: replyAdjusted.wantsReply,
    mode: replyAdjusted.mode,
    meta: sanitized.meta
  };
}

export {
  LEGACY_EMPTY_RESPONSE,
  SAFE_EMPTY_FALLBACK,
  TELEGRAM_TEXT_LIMIT,
  sanitizeOutboundText,
  sanitizeTelegramOutboundPayload,
  truncateOutboundText
};
