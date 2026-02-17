'use strict';

/**
 * FreeComputeCloud — Normalized Provider Adapter
 *
 * Translates between the internal call interface and the external
 * provider protocol. Supports OpenAI-compatible and vendor-native
 * (Gemini) protocols.
 *
 * Interface contract (same as existing providers):
 *   async health()  → { ok: boolean, reason?: string, models?: string[] }
 *   async call({ messages, metadata })  → { text, raw, usage }
 *
 * The adapter reads its config from a catalog entry at construction time.
 * No provider-specific code paths — protocol dispatches generically.
 */

const http = require('node:http');
const https = require('node:https');
const { URL } = require('node:url');
const { redactIfSensitive } = require('./config');

class ProviderAdapter {
  /**
   * @param {object} catalogEntry - A provider catalog entry
   * @param {object} [options]
   * @param {object} [options.env] - Environment variables source
   * @param {function} [options.emitEvent] - (eventType, payload) => void
   */
  constructor(catalogEntry, options = {}) {
    this.entry = catalogEntry;
    this.providerId = catalogEntry.provider_id;
    this.protocol = catalogEntry.protocol;
    // Non-enumerable: never leak env or callbacks via JSON.stringify
    Object.defineProperty(this, '_env', {
      value: options.env || process.env, writable: false, enumerable: false
    });
    Object.defineProperty(this, '_emitEvent', {
      value: options.emitEvent || (() => {}), writable: true, enumerable: false
    });

    // Resolve base URL
    this.baseUrl = this._env[catalogEntry.base_url.env_override]
      || catalogEntry.base_url.default;

    // Resolve auth — non-enumerable so it never leaks via JSON.stringify
    Object.defineProperty(this, '_authToken', {
      value: (catalogEntry.auth && catalogEntry.auth.env_var)
        ? (this._env[catalogEntry.auth.env_var] || null)
        : null,
      writable: true,
      enumerable: false,
      configurable: false
    });

    // Resolve model ID (first concrete model or AUTO_DISCOVER)
    const firstModel = catalogEntry.models[0];
    this._defaultModelId = firstModel ? firstModel.model_id : null;

    // Healthcheck config
    this._hc = catalogEntry.healthcheck || {};
  }

  /**
   * Health check: probe the provider for liveness.
   * @returns {Promise<{ ok: boolean, reason?: string, models?: string[] }>}
   */
  async health() {
    try {
      if (this._hc.type === 'openai_compatible' || this.protocol === 'openai_compatible') {
        return await this._healthOpenAI();
      }
      if (this._hc.type === 'anthropic_messages' || this.protocol === 'anthropic_messages') {
        return await this._healthAnthropic();
      }
      if (this.providerId === 'gemini') {
        return await this._healthGemini();
      }
      // Fallback: try OpenAI-compatible probe
      return await this._healthOpenAI();
    } catch (err) {
      return { ok: false, reason: err.message };
    }
  }

  /**
   * Make an inference call.
   * @param {object} params
   * @param {Array} params.messages - Chat messages [{role, content}]
   * @param {object} [params.metadata] - { model, maxTokens, temperature }
   * @returns {Promise<{ text: string, raw: object, usage: object }>}
   */
  async call({ messages = [], metadata = {} }) {
    const model = metadata.model || this._defaultModelId;
    const maxTokens = metadata.maxTokens || metadata.max_tokens || 4096;
    const temperature = typeof metadata.temperature === 'number'
      ? metadata.temperature : 0.7;

    const startMs = Date.now();
    let result;

    try {
      if (this.protocol === 'openai_compatible') {
        result = await this._callOpenAI({ messages, model, maxTokens, temperature });
      } else if (this.protocol === 'anthropic_messages') {
        result = await this._callAnthropic({ messages, model, maxTokens, temperature });
      } else if (this.providerId === 'gemini') {
        result = await this._callGemini({ messages, model, maxTokens, temperature });
      } else {
        throw new Error(`unsupported protocol: ${this.protocol}`);
      }
    } catch (err) {
      const elapsed = Date.now() - startMs;
      this._emitEvent('freecompute_call_error', {
        provider_id: this.providerId,
        model,
        error: err.message,
        elapsed_ms: elapsed
      });
      throw err;
    }

    const elapsed = Date.now() - startMs;
    this._emitEvent('freecompute_call', {
      provider_id: this.providerId,
      model: result.model || model,
      tokens_in: result.usage.inputTokens,
      tokens_out: result.usage.outputTokens,
      elapsed_ms: elapsed,
      ok: true
    });

    return result;
  }

  // ── OpenAI-Compatible Protocol ──────────────────────────────────────

  async _healthOpenAI() {
    const modelsUrl = this.baseUrl.replace(/\/+$/, '') +
      ((this._hc.endpoints && this._hc.endpoints.models) || '/models');

    const data = await this._httpGet(modelsUrl, {
      timeoutMs: (this._hc.timeouts_ms && this._hc.timeouts_ms.read) || 6000
    });

    const models = (data && data.data && Array.isArray(data.data))
      ? data.data.map((m) => m.id).filter(Boolean)
      : [];

    return { ok: true, models };
  }

  async _callOpenAI({ messages, model, maxTokens, temperature }) {
    const chatUrl = this.baseUrl.replace(/\/+$/, '') + '/chat/completions';

    const body = {
      model,
      messages,
      max_tokens: maxTokens,
      temperature,
      stream: false
    };

    const data = await this._httpPost(chatUrl, body, {
      timeoutMs: (this._hc.timeouts_ms && this._hc.timeouts_ms.read) || 30000
    });

    const choice = (data.choices && data.choices[0]) || {};
    const message = choice.message || {};
    const usage = data.usage || {};

    return {
      text: message.content || '',
      model: data.model || model,
      raw: data,
      usage: {
        inputTokens: usage.prompt_tokens || 0,
        outputTokens: usage.completion_tokens || 0,
        totalTokens: usage.total_tokens || 0,
        estimatedCostUsd: 0 // Free tier; computed upstream if needed
      }
    };
  }

  // ── Anthropic Messages Protocol ────────────────────────────────────

  async _healthAnthropic() {
    const modelsPath = (this._hc.endpoints && this._hc.endpoints.models) || '/v1/models';
    const modelsUrl = this.baseUrl.replace(/\/+$/, '') + modelsPath;

    const data = await this._httpGet(modelsUrl, {
      timeoutMs: (this._hc.timeouts_ms && this._hc.timeouts_ms.read) || 9000
    });

    const models = Array.isArray(data && data.data)
      ? data.data.map((m) => m.id).filter(Boolean)
      : [];

    return { ok: true, models };
  }

  async _callAnthropic({ messages, model, maxTokens, temperature }) {
    const messagesPath = (this._hc.endpoints && this._hc.endpoints.messages) || '/v1/messages';
    const url = this.baseUrl.replace(/\/+$/, '') + messagesPath;

    const mappedMessages = messages.map((m) => ({
      role: m.role === 'assistant' ? 'assistant' : 'user',
      content: String(m.content || '')
    }));

    const body = {
      model,
      messages: mappedMessages,
      max_tokens: maxTokens,
      temperature
    };

    const data = await this._httpPost(url, body, {
      timeoutMs: (this._hc.timeouts_ms && this._hc.timeouts_ms.read) || 30000
    });

    const content = Array.isArray(data && data.content) ? data.content : [];
    const text = content
      .filter((part) => part && part.type === 'text')
      .map((part) => part.text || '')
      .join('');
    const usage = data.usage || {};

    return {
      text,
      model: data.model || model,
      raw: data,
      usage: {
        inputTokens: usage.input_tokens || 0,
        outputTokens: usage.output_tokens || 0,
        totalTokens: (usage.input_tokens || 0) + (usage.output_tokens || 0),
        estimatedCostUsd: 0
      }
    };
  }

  // ── Gemini Protocol ─────────────────────────────────────────────────

  async _healthGemini() {
    const modelsUrl = this.baseUrl.replace(/\/+$/, '') +
      '/v1beta/models?key=' + (this._authToken || '');

    const data = await this._httpGet(modelsUrl, {
      timeoutMs: (this._hc.timeouts_ms && this._hc.timeouts_ms.read) || 8000,
      skipAuth: true // API key is in the URL for Gemini
    });

    const models = (data && data.models && Array.isArray(data.models))
      ? data.models.map((m) => m.name).filter(Boolean)
      : [];

    return { ok: true, models };
  }

  async _callGemini({ messages, model, maxTokens, temperature }) {
    // Gemini generateContent endpoint
    const url = this.baseUrl.replace(/\/+$/, '') +
      `/v1beta/models/${model}:generateContent?key=` + (this._authToken || '');

    // Convert OpenAI-style messages to Gemini contents
    const contents = messages.map((m) => ({
      role: m.role === 'assistant' ? 'model' : 'user',
      parts: [{ text: m.content || '' }]
    }));

    const body = {
      contents,
      generationConfig: {
        maxOutputTokens: maxTokens,
        temperature
      }
    };

    const data = await this._httpPost(url, body, {
      timeoutMs: (this._hc.timeouts_ms && this._hc.timeouts_ms.read) || 30000,
      skipAuth: true // API key is in the URL
    });

    const candidate = (data.candidates && data.candidates[0]) || {};
    const parts = (candidate.content && candidate.content.parts) || [];
    const text = parts.map((p) => p.text || '').join('');
    const usageMeta = data.usageMetadata || {};

    return {
      text,
      model,
      raw: data,
      usage: {
        inputTokens: usageMeta.promptTokenCount || 0,
        outputTokens: usageMeta.candidatesTokenCount || 0,
        totalTokens: usageMeta.totalTokenCount || 0,
        estimatedCostUsd: 0
      }
    };
  }

  // ── HTTP Helpers ────────────────────────────────────────────────────

  _buildHeaders(skipAuth) {
    const headers = { 'Content-Type': 'application/json' };
    if (!skipAuth && this._authToken) {
      const authType = this.entry.auth && this.entry.auth.type;
      if (authType === 'api_key') {
        headers['x-api-key'] = this._authToken;
      } else {
        headers['Authorization'] = `Bearer ${this._authToken}`;
      }
    }
    // OpenRouter requires HTTP-Referer and X-Title
    if (this.providerId === 'openrouter') {
      headers['HTTP-Referer'] = 'https://github.com/openclaw';
      headers['X-Title'] = 'OpenClaw';
    }
    if (this.protocol === 'anthropic_messages') {
      headers['anthropic-version'] = '2023-06-01';
    }
    return headers;
  }

  _httpGet(url, options = {}) {
    return this._httpRequest('GET', url, null, options);
  }

  _httpPost(url, body, options = {}) {
    return this._httpRequest('POST', url, body, options);
  }

  _httpRequest(method, urlStr, body, options = {}) {
    return new Promise((resolve, reject) => {
      const parsed = new URL(urlStr);
      const isHttps = parsed.protocol === 'https:';
      const mod = isHttps ? https : http;
      const headers = {
        ...this._buildHeaders(options.skipAuth),
        ...(options.headers || {})
      };

      const payload = body ? JSON.stringify(body) : null;
      if (payload) {
        headers['Content-Length'] = Buffer.byteLength(payload);
      }

      const req = mod.request({
        hostname: parsed.hostname,
        port: parsed.port || (isHttps ? 443 : 80),
        path: parsed.pathname + parsed.search,
        method,
        headers,
        timeout: options.timeoutMs || 30000
      }, (res) => {
        let data = '';
        res.on('data', (chunk) => { data += chunk; });
        res.on('end', () => {
          try {
            resolve(JSON.parse(data));
          } catch (_) {
            reject(new Error(`invalid JSON from ${this.providerId}: ${data.slice(0, 200)}`));
          }
        });
      });

      req.on('timeout', () => {
        req.destroy();
        reject(new Error(`timeout connecting to ${this.providerId}`));
      });
      req.on('error', (err) => reject(err));

      if (payload) req.write(payload);
      req.end();
    });
  }
}

module.exports = { ProviderAdapter };
