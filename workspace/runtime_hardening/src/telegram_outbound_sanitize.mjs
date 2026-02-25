import crypto from 'node:crypto';

const TELEGRAM_TEXT_LIMIT = 4096;
const LEGACY_EMPTY_RESPONSE = 'No response generated. Please try again.';
const SAFE_EMPTY_FALLBACK =
  'I didn\'t generate a reply that time. If you mean the list from yesterday, I can regenerate it: top 10 or full list?';
const INTERNAL_PREFIX_RE = /^\s*(Reasoning|Analysis|Plan|Thoughts|Chain-of-thought|Scratchpad)\s*:/i;
const INTERNAL_TAG_START_RE = /^\s*(<analysis>|<think>|```analysis)\b/i;

function normalizeBlankLines(text) {
  return text.replace(/\n{3,}/g, '\n\n');
}

function stripTaggedBlocks(text) {
  let out = text;
  out = out.replace(/<analysis>[\s\S]*?<\/analysis>/gi, '');
  out = out.replace(/<think>[\s\S]*?<\/think>/gi, '');
  out = out.replace(/```analysis[\s\S]*?```/gi, '');
  return out;
}

function truncateTelegramText(text, maxLen = TELEGRAM_TEXT_LIMIT) {
  if (text.length <= maxLen) return text;
  if (maxLen <= 1) return '…';
  return `${text.slice(0, Math.max(0, maxLen - 1))}…`;
}

function sanitizeOutboundText(text) {
  const source = typeof text === 'string' ? text : String(text ?? '');
  if (!source.trim()) return '';

  let cleaned = stripTaggedBlocks(source);
  const lines = cleaned.split(/\r?\n/);

  let cutoff = -1;
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i] || '';
    if (INTERNAL_PREFIX_RE.test(line) || INTERNAL_TAG_START_RE.test(line)) {
      cutoff = i;
      break;
    }
  }

  if (cutoff >= 0) {
    cleaned = lines.slice(0, cutoff).join('\n');
  }

  cleaned = normalizeBlankLines(cleaned).trim();
  if (cleaned === LEGACY_EMPTY_RESPONSE) return '';

  return truncateTelegramText(cleaned);
}

function createCorrelationId() {
  return `tg-${Date.now().toString(36)}-${crypto.randomBytes(3).toString('hex')}`;
}

function sanitizeTelegramOutboundPayload(payload, options = {}) {
  if (!payload || typeof payload !== 'object') {
    return {
      payload,
      changed: false,
      usedFallback: false,
      correlationId: createCorrelationId()
    };
  }

  const next = { ...payload };
  const meta = {
    correlation_id: options.correlationId || createCorrelationId(),
    chat_id: payload.chat_id ?? payload.chatId ?? null,
    message_id: payload.reply_to_message_id ?? payload.replyToMessageId ?? null
  };

  let changed = false;
  let usedFallback = false;

  for (const field of ['text', 'caption']) {
    if (typeof next[field] !== 'string') continue;
    const sanitized = sanitizeOutboundText(next[field]);
    if (!sanitized) {
      next[field] = SAFE_EMPTY_FALLBACK;
      usedFallback = true;
      changed = true;
    } else if (sanitized !== next[field]) {
      next[field] = sanitized;
      changed = true;
    }
  }

  if (usedFallback && options.logger) {
    options.logger.error('telegram_outbound_empty_or_stripped_response', {
      reason: 'EMPTY_OR_STRIPPED_RESPONSE',
      ...meta
    });
  } else if (changed && options.logger) {
    options.logger.warn('telegram_outbound_sanitized', {
      reason: 'INTERNAL_CONTENT_STRIPPED_OR_TRUNCATED',
      ...meta
    });
  }

  return {
    payload: next,
    changed,
    usedFallback,
    correlationId: meta.correlation_id
  };
}

export {
  LEGACY_EMPTY_RESPONSE,
  SAFE_EMPTY_FALLBACK,
  TELEGRAM_TEXT_LIMIT,
  sanitizeOutboundText,
  sanitizeTelegramOutboundPayload,
  truncateTelegramText
};
