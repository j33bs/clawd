import crypto from 'node:crypto';

const LEGACY_EMPTY_RESPONSE = 'No response generated. Please try again.';
const SAFE_EMPTY_FALLBACK =
  'I didn\'t generate a reply that time. If you mean the list from yesterday, I can regenerate it: top 10 or full list?';

const CHANNEL_TEXT_LIMITS = Object.freeze({
  telegram: 4096,
  discord: 2000,
  slack: 40000,
  mattermost: 4000,
  msteams: 28000,
  teamchat: 4000,
  generic: 4096
});

const CHANNEL_TEXT_FIELDS = Object.freeze({
  telegram: ['text', 'caption'],
  discord: ['content'],
  slack: ['text'],
  mattermost: ['message', 'text'],
  msteams: ['text', 'summary'],
  teamchat: ['message', 'text'],
  generic: ['text', 'caption', 'content', 'message']
});

const INTERNAL_PREFIX_RE = /^\s*(Reasoning|Analysis|Plan|Thoughts|Chain-of-thought|Scratchpad)\s*:/i;
const INTERNAL_TAG_START_RE = /^\s*(<analysis>|<think>|```analysis)\b/i;

function normalizeChannel(channel) {
  const normalized = typeof channel === 'string' ? channel.trim().toLowerCase() : '';
  return Object.hasOwn(CHANNEL_TEXT_LIMITS, normalized) ? normalized : 'generic';
}

function defaultFallbackText(channel = 'generic') {
  normalizeChannel(channel);
  return SAFE_EMPTY_FALLBACK;
}

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

function truncateOutboundText(text, maxLen) {
  if (text.length <= maxLen) return text;
  if (maxLen <= 1) return '…';
  return `${text.slice(0, Math.max(0, maxLen - 1))}…`;
}

function sanitizeOutboundText(text, opts = {}) {
  const channel = normalizeChannel(opts.channel);
  const maxLength =
    Number.isInteger(opts.maxLength) && opts.maxLength > 0 ? opts.maxLength : CHANNEL_TEXT_LIMITS[channel];
  const source = typeof text === 'string' ? text : String(text ?? '');
  const sourceTrimmed = source.trim();
  if (!sourceTrimmed) {
    return {
      text: '',
      stripped: false,
      reason: null,
      meta: {
        channel,
        strippedInternal: false,
        truncated: false,
        changed: source.length > 0,
        matchedLegacySentinel: false
      }
    };
  }

  const matchedLegacySentinel = sourceTrimmed === LEGACY_EMPTY_RESPONSE;
  let cleaned = stripTaggedBlocks(source);
  let strippedInternal = cleaned !== source;
  const lines = cleaned.split(/\r?\n/);
  let cutoff = -1;
  for (let idx = 0; idx < lines.length; idx += 1) {
    const line = lines[idx] || '';
    if (INTERNAL_PREFIX_RE.test(line) || INTERNAL_TAG_START_RE.test(line)) {
      cutoff = idx;
      break;
    }
  }
  if (cutoff >= 0) {
    cleaned = lines.slice(0, cutoff).join('\n');
    strippedInternal = true;
  }

  cleaned = normalizeBlankLines(cleaned).trim();
  if (matchedLegacySentinel) cleaned = '';
  const truncated = cleaned.length > maxLength;
  const textOut = truncateOutboundText(cleaned, maxLength);

  return {
    text: textOut,
    stripped: strippedInternal,
    reason: strippedInternal ? 'STRIPPED_INTERNAL' : matchedLegacySentinel ? 'EMPTY_OR_STRIPPED' : null,
    meta: {
      channel,
      strippedInternal,
      truncated,
      changed: textOut !== source,
      matchedLegacySentinel
    }
  };
}

function ensureNonEmptyOutbound(text, fallbackText = SAFE_EMPTY_FALLBACK) {
  const source = typeof text === 'string' ? text : String(text ?? '');
  const trimmed = source.trim();
  if (!trimmed || trimmed === LEGACY_EMPTY_RESPONSE) {
    return fallbackText;
  }
  return source;
}

function createCorrelationId(channel) {
  const prefix = normalizeChannel(channel).slice(0, 2) || 'ch';
  return `${prefix}-${Date.now().toString(36)}-${crypto.randomBytes(3).toString('hex')}`;
}

function resolveTextFields(channel, extraFields) {
  const normalized = normalizeChannel(channel);
  const defaults = CHANNEL_TEXT_FIELDS[normalized] || CHANNEL_TEXT_FIELDS.generic;
  if (!Array.isArray(extraFields) || extraFields.length === 0) return defaults;
  return [...new Set([...defaults, ...extraFields])];
}

function resolveMessageId(payload) {
  if (!payload || typeof payload !== 'object') return null;
  if (payload.reply_to_message_id != null) return payload.reply_to_message_id;
  if (payload.replyToMessageId != null) return payload.replyToMessageId;
  if (payload.message_id != null) return payload.message_id;
  if (payload.messageReference?.message_id != null) return payload.messageReference.message_id;
  if (payload.reply_parameters?.message_id != null) return payload.reply_parameters.message_id;
  if (typeof payload.reply_parameters === 'string') {
    try {
      const parsed = JSON.parse(payload.reply_parameters);
      if (parsed && parsed.message_id != null) return parsed.message_id;
    } catch {}
  }
  return null;
}

function resolveChatId(payload) {
  if (!payload || typeof payload !== 'object') return null;
  return (
    payload.chat_id ??
    payload.chatId ??
    payload.channel_id ??
    payload.channelId ??
    payload.channel ??
    payload.thread_ts ??
    payload.conversation ??
    null
  );
}

function sanitizeOutboundPayload(payload, opts = {}) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return {
      payload,
      changed: false,
      usedFallback: false,
      meta: {
        reason: null,
        channel: normalizeChannel(opts.channel),
        correlation_id: createCorrelationId(opts.channel),
        chat_id: null,
        message_id: null
      }
    };
  }

  const channel = normalizeChannel(opts.channel);
  const fields = resolveTextFields(channel, opts.textFields);
  const correlationId = opts.correlationId || createCorrelationId(channel);
  const next = { ...payload };
  let changed = false;
  let usedFallback = false;
  let strippedInternal = false;
  let truncated = false;
  let matchedLegacySentinel = false;
  const fallbackText = defaultFallbackText(channel);

  for (const field of fields) {
    if (typeof next[field] !== 'string') continue;
    const { text, meta } = sanitizeOutboundText(next[field], {
      channel,
      maxLength: opts.maxLength
    });
    const ensured = ensureNonEmptyOutbound(text, fallbackText);
    if (ensured === fallbackText) usedFallback = true;
    if (meta.strippedInternal) strippedInternal = true;
    if (meta.truncated) truncated = true;
    if (meta.matchedLegacySentinel) matchedLegacySentinel = true;
    if (ensured !== next[field]) {
      next[field] = ensured;
      changed = true;
    }
  }

  const reason = usedFallback ? 'EMPTY_OR_STRIPPED' : strippedInternal ? 'STRIPPED_INTERNAL' : null;
  const meta = {
    reason,
    channel,
    correlation_id: correlationId,
    chat_id: resolveChatId(next),
    message_id: resolveMessageId(next),
    strippedInternal,
    truncated,
    matchedLegacySentinel
  };

  if (reason === 'EMPTY_OR_STRIPPED' && opts.logger) {
    opts.logger.error('outbound_empty_or_stripped_response', meta);
  } else if (reason === 'STRIPPED_INTERNAL' && opts.logger) {
    opts.logger.warn('outbound_internal_content_stripped', meta);
  }

  return {
    payload: next,
    changed,
    usedFallback,
    meta
  };
}

export {
  CHANNEL_TEXT_FIELDS,
  CHANNEL_TEXT_LIMITS,
  LEGACY_EMPTY_RESPONSE,
  SAFE_EMPTY_FALLBACK,
  defaultFallbackText,
  ensureNonEmptyOutbound,
  normalizeChannel,
  sanitizeOutboundPayload,
  sanitizeOutboundText,
  truncateOutboundText
};
