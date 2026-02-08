const { normalizeProviderError } = require('../normalize_error');

const DEFAULT_BASE_URL = 'http://127.0.0.1:11434';
const DEFAULT_MODEL = 'llama3.2:3b-instruct';
const DEFAULT_MAX_TOKENS = 256;
const MAX_TOKENS_CAP = 512;
const DEFAULT_TEMPERATURE = 0.2;
const DEFAULT_CONTEXT_WINDOW = 2048;
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

class LocalOllamaProvider {
  constructor(options = {}) {
    this.baseUrl = (options.baseUrl || process.env.OLLAMA_HOST || DEFAULT_BASE_URL).replace(/\/$/, '');
    this.defaultModel = options.defaultModel || process.env.OPENCLAW_LOCAL_MODEL || DEFAULT_MODEL;
    this.maxTokensDefault = Number(options.maxTokensDefault ?? DEFAULT_MAX_TOKENS);
    this.maxTokensCap = Number(options.maxTokensCap ?? MAX_TOKENS_CAP);
    this.temperatureDefault = Number(options.temperatureDefault ?? DEFAULT_TEMPERATURE);
    this.contextWindow = Number(options.contextWindow ?? DEFAULT_CONTEXT_WINDOW);
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
      const response = await fetch(`${this.baseUrl}/api/tags`, {
        method: 'GET',
        signal: controller.signal
      });
      clearTimeout(timer);
      if (!response.ok) {
        const error = new Error(`Ollama health check failed: ${response.status}`);
        error.status = response.status;
        throw error;
      }
      const value = { ok: true };
      this.healthCache = { timestamp: now, value };
      return value;
    } catch (error) {
      clearTimeout(timer);
      const normalized = normalizeProviderError(error, 'LOCAL_OLLAMA');
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

    if (simulation.localOllamaError) {
      const simulated = new Error(`Simulated Ollama error: ${simulation.localOllamaError}`);
      simulated.code = simulation.localOllamaError;
      throw simulated;
    }

    return this.enqueue(async () => this.callInternal({ messages, metadata }));
  }

  async callInternal({ messages = [], metadata = {} }) {
    const model =
      metadata.localModel ||
      metadata.ollamaModel ||
      process.env.OPENCLAW_LOCAL_MODEL ||
      this.defaultModel;

    const requestedMaxTokens = metadata.maxTokens || metadata.max_tokens || this.maxTokensDefault;
    const cappedMaxTokens = clampNumber(requestedMaxTokens, 1, this.maxTokensCap) ?? this.maxTokensDefault;
    const temperature = clampNumber(metadata.temperature ?? this.temperatureDefault, 0, 1) ?? this.temperatureDefault;
    const contextWindow = clampNumber(metadata.contextWindow ?? this.contextWindow, 256, DEFAULT_CONTEXT_WINDOW) ??
      DEFAULT_CONTEXT_WINDOW;

    const body = {
      model,
      messages: mapMessages(messages),
      stream: false,
      options: {
        temperature,
        num_predict: cappedMaxTokens,
        num_ctx: contextWindow
      }
    };

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await fetch(`${this.baseUrl}/api/chat`, {
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
        const error = new Error(payload?.error || `Ollama request failed: ${response.status}`);
        error.status = response.status;
        error.code = payload?.error || null;
        error.body = payload;
        throw error;
      }

      const text = payload && payload.message && typeof payload.message.content === 'string'
        ? payload.message.content
        : '';

      const inputTokens = payload.prompt_eval_count || 0;
      const outputTokens = payload.eval_count || 0;

      return {
        text,
        raw: payload,
        usage: {
          inputTokens,
          outputTokens,
          totalTokens: inputTokens + outputTokens,
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

module.exports = LocalOllamaProvider;
