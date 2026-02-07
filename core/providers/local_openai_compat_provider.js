const { normalizeProviderError } = require('../normalize_error');

const DEFAULT_BASE_URL = 'http://127.0.0.1:1234/v1';
const DEFAULT_MODEL = 'local-model';
const DEFAULT_MAX_TOKENS = 256;
const MAX_TOKENS_CAP = 512;
const DEFAULT_TEMPERATURE = 0.2;
const DEFAULT_TIMEOUT_MS = 15000;
const DEFAULT_HEALTH_TIMEOUT_MS = 1000;
const DEFAULT_HEALTH_CACHE_MS = 30000;

function normalizeMessageContent(content) {
  if (typeof content === 'string') {
    return content;
  }
  if (Array.isArray(content)) {
    return content
      .map((item) => {
        if (typeof item === 'string') {
          return item;
        }
        if (item && typeof item.text === 'string') {
          return item.text;
        }
        return '';
      })
      .join('\n');
  }
  return '';
}

function mapMessages(messages) {
  const mapped = [];

  messages.forEach((message) => {
    const role = String(message.role || 'user').toLowerCase();
    const content = normalizeMessageContent(message.content);
    if (!content) {
      return;
    }
    if (role === 'system') {
      mapped.push({ role: 'system', content });
      return;
    }
    if (role === 'assistant') {
      mapped.push({ role: 'assistant', content });
      return;
    }
    mapped.push({ role: 'user', content });
  });

  if (mapped.length === 0) {
    mapped.push({ role: 'user', content: '' });
  }

  return mapped;
}

function clampNumber(value, minValue, maxValue) {
  const numeric = Number(value);
  if (Number.isNaN(numeric)) {
    return null;
  }
  return Math.min(Math.max(numeric, minValue), maxValue);
}

function joinUrl(baseUrl, path) {
  return `${String(baseUrl).replace(/\/$/, '')}${path}`;
}

class LocalOpenAiCompatProvider {
  constructor(options = {}) {
    this.baseUrl = (options.baseUrl || process.env.OPENCLAW_LOCAL_ENDPOINT || DEFAULT_BASE_URL).replace(/\/$/, '');
    this.defaultModel = options.defaultModel || process.env.OPENCLAW_LOCAL_MODEL || DEFAULT_MODEL;
    this.maxTokensDefault = Number(options.maxTokensDefault ?? DEFAULT_MAX_TOKENS);
    this.maxTokensCap = Number(options.maxTokensCap ?? MAX_TOKENS_CAP);
    this.temperatureDefault = Number(options.temperatureDefault ?? DEFAULT_TEMPERATURE);
    this.timeoutMs = Number(options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
    this.healthTimeoutMs = Number(options.healthTimeoutMs ?? DEFAULT_HEALTH_TIMEOUT_MS);
    this.healthCacheMs = Number(options.healthCacheMs ?? DEFAULT_HEALTH_CACHE_MS);
    this.queue = Promise.resolve();
    this.healthCache = null;
  }

  async health() {
    const now = Date.now();
    if (this.healthCache && now - this.healthCache.timestamp < this.healthCacheMs) {
      return this.healthCache.value;
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.healthTimeoutMs);

    try {
      const response = await fetch(joinUrl(this.baseUrl, '/models'), {
        method: 'GET',
        signal: controller.signal
      });
      clearTimeout(timer);
      if (!response.ok) {
        const error = new Error(`Local OpenAI health check failed: ${response.status}`);
        error.status = response.status;
        throw error;
      }
      const value = { ok: true };
      this.healthCache = { timestamp: now, value };
      return value;
    } catch (error) {
      clearTimeout(timer);
      const normalized = normalizeProviderError(error, 'LOCAL_OPENAI_COMPAT');
      const value = {
        ok: false,
        reason: normalized.code,
        status: normalized.status,
        rawCode: normalized.rawCode
      };
      this.healthCache = { timestamp: now, value };
      return value;
    }
  }

  async call({ messages = [], metadata = {} }) {
    const simulation = metadata && metadata.simulation ? metadata.simulation : {};

    if (simulation.localOpenAiError) {
      const simulated = new Error(`Simulated Local OpenAI error: ${simulation.localOpenAiError}`);
      simulated.code = simulation.localOpenAiError;
      throw simulated;
    }

    return this.enqueue(async () => this.callInternal({ messages, metadata }));
  }

  async callInternal({ messages = [], metadata = {} }) {
    const model = metadata.localModel || process.env.OPENCLAW_LOCAL_MODEL || this.defaultModel;
    const requestedMaxTokens = metadata.maxTokens || metadata.max_tokens || this.maxTokensDefault;
    const cappedMaxTokens = clampNumber(requestedMaxTokens, 1, this.maxTokensCap) ?? this.maxTokensDefault;
    const temperature = clampNumber(metadata.temperature ?? this.temperatureDefault, 0, 1) ?? this.temperatureDefault;

    const body = {
      model,
      messages: mapMessages(messages),
      max_tokens: cappedMaxTokens,
      temperature,
      stream: false
    };

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await fetch(joinUrl(this.baseUrl, '/chat/completions'), {
        method: 'POST',
        headers: {
          'content-type': 'application/json'
        },
        body: JSON.stringify(body),
        signal: controller.signal
      });

      clearTimeout(timer);

      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        const error = new Error(payload?.error?.message || `Local OpenAI request failed: ${response.status}`);
        error.status = response.status;
        error.code = payload?.error?.type || null;
        error.body = payload;
        throw error;
      }

      const choice = Array.isArray(payload.choices) ? payload.choices[0] : null;
      const text = choice && choice.message && typeof choice.message.content === 'string'
        ? choice.message.content
        : '';

      const usage = payload.usage || {};

      return {
        text,
        raw: payload,
        usage: {
          inputTokens: usage.prompt_tokens || 0,
          outputTokens: usage.completion_tokens || 0,
          totalTokens: usage.total_tokens || (usage.prompt_tokens || 0) + (usage.completion_tokens || 0),
          estimatedCostUsd: 0
        }
      };
    } catch (error) {
      clearTimeout(timer);
      throw error;
    }
  }

  enqueue(fn) {
    const run = this.queue.then(fn, fn);
    this.queue = run.catch(() => {});
    return run;
  }
}

module.exports = LocalOpenAiCompatProvider;
