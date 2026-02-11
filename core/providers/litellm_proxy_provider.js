'use strict';

const { normalizeProviderError } = require('../normalize_error');

const DEFAULT_BASE_URL = 'http://127.0.0.1:4000/v1';
const DEFAULT_MODEL = 'gpt-4o-mini';
const DEFAULT_MAX_TOKENS = 512;
const DEFAULT_TIMEOUT_MS = 30000;
const DEFAULT_HEALTH_TIMEOUT_MS = 2000;
const DEFAULT_HEALTH_CACHE_MS = 15000;

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

function mapMessages(messages = []) {
  const mapped = [];
  for (const message of messages) {
    if (!message) {
      continue;
    }
    const role = String(message.role || 'user').toLowerCase();
    const content = normalizeMessageContent(message.content);
    mapped.push({
      role: role === 'assistant' ? 'assistant' : role === 'system' ? 'system' : 'user',
      content
    });
  }
  return mapped.length > 0 ? mapped : [{ role: 'user', content: '' }];
}

function joinUrl(baseUrl, suffix) {
  return `${String(baseUrl || '').replace(/\/$/, '')}${suffix}`;
}

class LiteLlmProxyProvider {
  constructor(options = {}) {
    this.baseUrl = options.baseUrl || process.env.SYSTEM2_LITELLM_ENDPOINT || DEFAULT_BASE_URL;
    this.defaultModel = options.defaultModel || process.env.SYSTEM2_LITELLM_MODEL || DEFAULT_MODEL;
    this.timeoutMs = Number(options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
    this.healthTimeoutMs = Number(options.healthTimeoutMs ?? DEFAULT_HEALTH_TIMEOUT_MS);
    this.healthCacheMs = Number(options.healthCacheMs ?? DEFAULT_HEALTH_CACHE_MS);
    this.apiKeyEnv = options.apiKeyEnv || process.env.SYSTEM2_LITELLM_API_KEY_ENV || 'LITELLM_API_KEY';
    this.healthCache = null;
  }

  resolveApiKey(metadata = {}) {
    if (metadata && metadata.litellmApiKey) {
      return String(metadata.litellmApiKey);
    }
    return process.env[this.apiKeyEnv] || null;
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

      const value = response.ok
        ? { ok: true }
        : { ok: false, reason: 'health_http_error', status: response.status };
      this.healthCache = { timestamp: now, value };
      return value;
    } catch (error) {
      clearTimeout(timer);
      const normalized = normalizeProviderError(error, 'LITELLM_PROXY');
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

  async call({ messages = [], metadata = {}, allowNetwork = true }) {
    if (!allowNetwork) {
      const error = new Error('Network disabled for LiteLLM proxy');
      error.code = 'NETWORK_DISABLED';
      throw error;
    }

    const model = metadata.litellmModel || metadata.model || this.defaultModel;
    const maxTokens = Number(metadata.maxTokens || metadata.max_tokens || DEFAULT_MAX_TOKENS);
    const apiKey = this.resolveApiKey(metadata);

    const headers = {
      'content-type': 'application/json'
    };
    if (apiKey) {
      headers.authorization = `Bearer ${apiKey}`;
    }

    const body = {
      model,
      messages: mapMessages(messages),
      max_tokens: maxTokens,
      temperature: Number(metadata.temperature ?? 0.2),
      stream: false
    };

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await fetch(joinUrl(this.baseUrl, '/chat/completions'), {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
        signal: controller.signal
      });
      const payload = await response.json().catch(() => ({}));
      clearTimeout(timer);

      if (!response.ok) {
        const error = new Error(payload?.error?.message || `LiteLLM call failed: ${response.status}`);
        error.status = response.status;
        error.code = payload?.error?.type || payload?.error?.code || null;
        error.body = payload;
        throw error;
      }

      const firstChoice = Array.isArray(payload.choices) ? payload.choices[0] : null;
      const text =
        firstChoice &&
        firstChoice.message &&
        typeof firstChoice.message.content === 'string'
          ? firstChoice.message.content
          : '';
      const usage = payload.usage || {};

      return {
        text,
        raw: payload,
        usage: {
          inputTokens: usage.prompt_tokens || 0,
          outputTokens: usage.completion_tokens || 0,
          totalTokens: usage.total_tokens || 0,
          estimatedCostUsd: null
        }
      };
    } catch (error) {
      clearTimeout(timer);
      throw error;
    }
  }
}

module.exports = LiteLlmProxyProvider;
