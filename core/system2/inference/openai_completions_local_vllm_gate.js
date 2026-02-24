'use strict';

function isLocalVllmTarget(baseUrl) {
  const value = String(baseUrl || '').trim().toLowerCase();
  if (!value) return false;
  if (value.includes('127.0.0.1:8001') || value.includes('localhost:8001') || value.includes('[::1]:8001')) {
    return true;
  }
  return value.includes('/vllm') || value.includes('vllm');
}

function isLocalVllmToolCallEnabled(env) {
  const value = String((env && env.OPENCLAW_VLLM_TOOLCALL) || process.env.OPENCLAW_VLLM_TOOLCALL || '0')
    .trim()
    .toLowerCase();
  return value === '1' || value === 'true' || value === 'yes' || value === 'on';
}

function applyLocalVllmToolPayloadGate(baseUrl, payload, env) {
  const next = payload && typeof payload === 'object' ? { ...payload } : {};
  if (!isLocalVllmTarget(baseUrl)) return next;
  if (isLocalVllmToolCallEnabled(env)) return next;
  delete next.tools;
  delete next.tool_choice;
  return next;
}

function isTruthyFlag(value, fallback) {
  const raw = value == null ? fallback : value;
  const normalized = String(raw || '').trim().toLowerCase();
  return normalized === '1' || normalized === 'true' || normalized === 'yes' || normalized === 'on';
}

function readEnvInt(value, fallback) {
  const parsed = Number.parseInt(String(value == null ? fallback : value), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function estimateMessageTokens(messages) {
  if (!Array.isArray(messages)) return 0;
  let totalChars = 0;
  for (const message of messages) {
    if (!message || typeof message !== 'object') continue;
    const roleChars = typeof message.role === 'string' ? message.role.length : 0;
    let contentChars = 0;
    const content = message.content;
    if (typeof content === 'string') {
      contentChars = content.length;
    } else if (Array.isArray(content)) {
      for (const part of content) {
        if (!part || typeof part !== 'object') continue;
        if (typeof part.text === 'string') contentChars += part.text.length;
        if (typeof part.input_text === 'string') contentChars += part.input_text.length;
      }
    } else if (content && typeof content === 'object') {
      if (typeof content.text === 'string') contentChars += content.text.length;
      if (typeof content.input_text === 'string') contentChars += content.input_text.length;
    }
    totalChars += roleChars + contentChars + 16;
  }
  return Math.ceil((totalChars / 4) * 1.2);
}

function truncateMessagesToBudget(messages, contextMax, completionTokens) {
  if (!Array.isArray(messages) || messages.length === 0) {
    return { messages: [], promptEstimate: 0, truncated: false };
  }
  const systems = [];
  const other = [];
  for (const msg of messages) {
    if (msg && typeof msg === 'object' && String(msg.role || '').toLowerCase() === 'system') {
      systems.push(msg);
    } else {
      other.push(msg);
    }
  }
  const kept = [...systems];
  for (let i = other.length - 1; i >= 0; i -= 1) {
    const candidate = [...systems, ...other.slice(i)];
    const est = estimateMessageTokens(candidate);
    if (est + completionTokens <= contextMax) {
      return { messages: candidate, promptEstimate: est, truncated: candidate.length < messages.length };
    }
  }
  const systemEst = estimateMessageTokens(systems);
  if (systemEst + completionTokens <= contextMax) {
    return { messages: systems, promptEstimate: systemEst, truncated: systems.length < messages.length };
  }
  return { messages: kept, promptEstimate: systemEst, truncated: kept.length < messages.length };
}

function applyLocalVllmTokenGuard(baseUrl, payload, env) {
  const next = payload && typeof payload === 'object' ? { ...payload } : {};
  if (!isLocalVllmTarget(baseUrl)) {
    return { payload: next, modified: false, diagnostic: null };
  }
  const mergedEnv = env || process.env;
  const guardEnabled = isTruthyFlag(mergedEnv.OPENCLAW_VLLM_TOKEN_GUARD, process.env.OPENCLAW_VLLM_TOKEN_GUARD || '0');
  if (!guardEnabled) {
    return { payload: next, modified: false, diagnostic: null };
  }
  const contextMax = readEnvInt(mergedEnv.OPENCLAW_VLLM_CONTEXT_MAX_TOKENS, 8192);
  const modeRaw = String(mergedEnv.OPENCLAW_VLLM_TOKEN_GUARD_MODE || 'reject').trim().toLowerCase();
  const mode = modeRaw === 'truncate' ? 'truncate' : 'reject';
  const requestedCompletion = readEnvInt(next.max_completion_tokens, 512);
  const maxAllowedCompletion = Math.max(1, contextMax - 256);
  const clampedCompletion = Math.min(requestedCompletion, maxAllowedCompletion);
  let modified = clampedCompletion !== next.max_completion_tokens;
  next.max_completion_tokens = clampedCompletion;
  const promptEstimate = estimateMessageTokens(next.messages);
  if (promptEstimate + clampedCompletion <= contextMax) {
    return {
      payload: next,
      modified,
      diagnostic: modified
        ? {
            event: 'vllm_token_guard',
            action: 'clamp',
            mode,
            context_max: contextMax,
            prompt_est: promptEstimate,
            max_completion_tokens: clampedCompletion
          }
        : null
    };
  }
  if (mode === 'truncate') {
    const truncated = truncateMessagesToBudget(next.messages, contextMax, clampedCompletion);
    next.messages = truncated.messages;
    modified = true;
    if (truncated.promptEstimate + clampedCompletion <= contextMax) {
      return {
        payload: next,
        modified,
        diagnostic: {
          event: 'vllm_token_guard',
          action: 'truncate',
          mode,
          context_max: contextMax,
          prompt_est: truncated.promptEstimate,
          max_completion_tokens: clampedCompletion,
          message_count_after: Array.isArray(truncated.messages) ? truncated.messages.length : 0
        }
      };
    }
  }
  const error = new Error('Local vLLM request exceeds context budget');
  error.code = 'VLLM_CONTEXT_BUDGET_EXCEEDED';
  error.prompt_est = promptEstimate;
  error.context_max = contextMax;
  error.requested_max_completion_tokens = clampedCompletion;
  error.mode = mode;
  throw error;
}

module.exports = {
  isLocalVllmTarget,
  isLocalVllmToolCallEnabled,
  applyLocalVllmToolPayloadGate,
  applyLocalVllmTokenGuard
};
