const TELEGRAM_REPLY_MODES = new Set(['never', 'auto', 'always']);
const COMMAND_LIKE_RE = /^\w+:\S*/;

function normalizeTelegramReplyMode(value, fallback = 'never') {
  const normalized = typeof value === 'string' ? value.trim().toLowerCase() : '';
  return TELEGRAM_REPLY_MODES.has(normalized) ? normalized : fallback;
}

function isCommandLikeMessage(text) {
  if (typeof text !== 'string') return false;
  const normalized = text.trim();
  if (!normalized) return false;
  return normalized.startsWith('/') || COMMAND_LIKE_RE.test(normalized);
}

function resolveIncomingTextHint(payload, incomingText) {
  if (typeof incomingText === 'string' && incomingText.trim()) return incomingText;
  if (!payload || typeof payload !== 'object') return '';
  const candidates = [
    payload.incoming_text,
    payload.incomingText,
    payload.source_text,
    payload.sourceText,
    payload.command_text,
    payload.commandText
  ];
  for (const value of candidates) {
    if (typeof value === 'string' && value.trim()) return value;
  }
  return '';
}

function shouldUseTelegramReply({ mode, incomingText, payload }) {
  const normalizedMode = normalizeTelegramReplyMode(mode);
  if (normalizedMode === 'always') return true;
  if (normalizedMode === 'never') return false;
  if (isCommandLikeMessage(incomingText)) return true;

  if (payload && typeof payload === 'object') {
    if (payload.force_reply === true || payload.force_reply === 'true') return true;
    const quoteText = payload.reply_parameters?.quote ?? payload.reply_parameters?.text ?? payload.quote_text;
    if (typeof quoteText === 'string' && quoteText.trim()) return true;
  }

  return false;
}

function hasTelegramReplyFields(payload) {
  if (!payload || typeof payload !== 'object') return false;
  return (
    Object.hasOwn(payload, 'reply_to_message_id') ||
    Object.hasOwn(payload, 'reply_parameters') ||
    Object.hasOwn(payload, 'replyToMessageId')
  );
}

function stripTelegramReplyFields(payload) {
  const next = { ...payload };
  delete next.reply_to_message_id;
  delete next.reply_parameters;
  delete next.replyToMessageId;
  return next;
}

function buildTelegramSendPayload(params = {}) {
  const source =
    params.payload && typeof params.payload === 'object' && !Array.isArray(params.payload) ? params.payload : {};
  const mode = normalizeTelegramReplyMode(params.mode);
  const incomingText = resolveIncomingTextHint(source, params.incomingText);
  const wantsReply = shouldUseTelegramReply({ mode, incomingText, payload: source });

  let payload = { ...source };
  if (!wantsReply) {
    payload = stripTelegramReplyFields(payload);
  } else if (Object.hasOwn(payload, 'reply_parameters')) {
    delete payload.reply_to_message_id;
    delete payload.replyToMessageId;
  } else if (payload.reply_to_message_id == null && payload.replyToMessageId != null) {
    payload.reply_to_message_id = payload.replyToMessageId;
    delete payload.replyToMessageId;
  }

  return {
    payload,
    mode,
    wantsReply,
    hadReplyFields: hasTelegramReplyFields(source)
  };
}

export {
  TELEGRAM_REPLY_MODES,
  buildTelegramSendPayload,
  hasTelegramReplyFields,
  isCommandLikeMessage,
  normalizeTelegramReplyMode,
  shouldUseTelegramReply,
  stripTelegramReplyFields
};
