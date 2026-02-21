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
const { TOOL_SUPPORT } = require('./schemas');
const { sanitizeToolPayload } = require('./tool_payload_sanitizer');

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
    const authEnvVar = (catalogEntry.auth && catalogEntry.auth.env_var) || null;
    const authAliasEnvVars = (catalogEntry.auth && Array.isArray(catalogEntry.auth.alias_env_vars))
      ? catalogEntry.auth.alias_env_vars
      : [];
    const resolvedAuthToken = authEnvVar
      ? (this._env[authEnvVar] || authAliasEnvVars.map((k) => this._env[k]).find((v) => !!v) || null)
      : null;
    Object.defineProperty(this, '_authToken', {
      value: resolvedAuthToken,
      writable: true,
      enumerable: false,
      configurable: false
    });

    // Resolve model ID (first concrete model or AUTO_DISCOVER)
    const firstModel = catalogEntry.models[0];
    this._defaultModelId = firstModel ? firstModel.model_id : null;

    // If this provider uses AUTO_DISCOVER, prefer operator-configured model env vars.
    // This avoids accidentally calling /chat/completions with model=AUTO_DISCOVER.
    if (this._defaultModelId === 'AUTO_DISCOVER') {
      const env = this._env || {};
      if (this.providerId === 'local_vllm' && env.OPENCLAW_VLLM_MODEL) {
        this._defaultModelId = env.OPENCLAW_VLLM_MODEL;
      }
      if (this.providerId === 'remote_vllm' && env.OPENCLAW_REMOTE_VLLM_MODEL) {
        this._defaultModelId = env.OPENCLAW_REMOTE_VLLM_MODEL;
      }
    }

    // Cache for model discovery (best-effort).
    this._discoveredModels = [];

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
    let model = metadata.model || this._defaultModelId;
    const maxTokens = metadata.maxTokens || metadata.max_tokens || 4096;
    const temperature = typeof metadata.temperature === 'number'
      ? metadata.temperature : 0.7;

    if (!model || model === 'AUTO_DISCOVER') {
      model = await this._resolveAutoModel();
    }

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

  /**
   * Deterministic "generation probe" (tiny request, short timeout).
   *
   * This is intentionally separate from health(), since /health and /models can
   * remain responsive while generation endpoints wedge/hang.
   *
   * @param {object} [options]
   * @param {string} [options.model]      - Optional model override
   * @param {string} [options.prompt]     - Prompt for /completions
   * @param {number} [options.timeoutMs]  - Hard timeout for probe
   * @returns {Promise<{ ok: boolean, reason?: string }>}
   */
  async generationProbe(options = {}) {
    if (this.protocol !== 'openai_compatible') {
      return { ok: false, reason: 'unsupported_protocol' };
    }

    const timeoutMs = typeof options.timeoutMs === 'number' ? options.timeoutMs : 5000;
    const prompt = typeof options.prompt === 'string' ? options.prompt : 'OK\n';

    let model = options.model || this._defaultModelId;
    if (!model || model === 'AUTO_DISCOVER') {
      model = await this._resolveAutoModel();
    }

    const url = this.baseUrl.replace(/\/+$/, '') + '/completions';
    const body = {
      model,
      prompt,
      max_tokens: 1,
      temperature: 0,
      stream: false
    };

    try {
      const data = await this._httpPost(url, body, { timeoutMs });
      // OpenAI-compatible completions: choices[0].text is the primary field.
      const choice = (data && data.choices && data.choices[0]) || null;
      const text = choice && typeof choice.text === 'string' ? choice.text : null;
      if (text === null) {
        return { ok: false, reason: 'parse_error' };
      }
      return { ok: true };
    } catch (err) {
      if (err && err.code === 'PROVIDER_TIMEOUT') return { ok: false, reason: 'timeout' };
      if (err && err.code === 'PROVIDER_HTTP_ERROR') return { ok: false, reason: `http_${err.statusCode || 'error'}` };
      const msg = String((err && err.message) || '');
      if (/invalid JSON/i.test(msg)) return { ok: false, reason: 'parse_error' };
      return { ok: false, reason: 'unknown' };
    }
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

    if (models.length > 0) {
      this._discoveredModels = models;
    }
    return { ok: true, models };
  }

  async _resolveAutoModel() {
    const env = this._env || {};
    // Operator overrides first.
    if (this.providerId === 'local_vllm' && env.OPENCLAW_VLLM_MODEL) return env.OPENCLAW_VLLM_MODEL;
    if (this.providerId === 'remote_vllm' && env.OPENCLAW_REMOTE_VLLM_MODEL) return env.OPENCLAW_REMOTE_VLLM_MODEL;

    // If we already discovered models, use the first deterministically.
    if (Array.isArray(this._discoveredModels) && this._discoveredModels.length > 0) {
      return this._discoveredModels[0];
    }

    // Best-effort discovery via /models.
    const h = await this.health();
    const models = (h && Array.isArray(h.models)) ? h.models : [];
    if (models.length > 0) {
      this._discoveredModels = models;
      return models[0];
    }

    const err = new Error(`no models available for provider ${this.providerId}`);
    err.code = 'PROVIDER_NO_MODELS';
    throw err;
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
      // Some local providers can take 60s+ for cold-start inference; allow per-provider chat timeout override.
      timeoutMs: (this._hc.timeouts_ms && this._hc.timeouts_ms.chat) || 30000
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
    const providerCaps = {
      tool_calls_supported: this._toolCallsSupported(body && body.model)
    };
    const sanitizedBody = sanitizeToolPayload(body, providerCaps);
    return this._httpRequest('POST', url, sanitizedBody, options);
  }

  _toolCallsSupported(modelId) {
    const models = Array.isArray(this.entry && this.entry.models) ? this.entry.models : [];
    if (models.length === 0) return null;

    const exact = modelId
      ? models.find((m) => m && m.model_id === modelId)
      : null;
    if (exact && exact.tool_support === TOOL_SUPPORT.NONE) return false;
    if (exact) return null;

    const allNone = models.every((m) => m && m.tool_support === TOOL_SUPPORT.NONE);
    return allNone ? false : null;
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
          if (res.statusCode < 200 || res.statusCode >= 300) {
            const err = new Error(`http ${res.statusCode} from ${this.providerId}`);
            err.code = 'PROVIDER_HTTP_ERROR';
            err.statusCode = res.statusCode;
            reject(err);
            return;
          }
          try {
            resolve(JSON.parse(data));
          } catch (_) {
            reject(new Error(`invalid JSON from ${this.providerId}: ${data.slice(0, 200)}`));
          }
        });
      });

      req.on('timeout', () => {
        req.destroy();
        const err = new Error(`timeout connecting to ${this.providerId}`);
        err.code = 'PROVIDER_TIMEOUT';
        reject(err);
      });
      req.on('error', (err) => reject(err));

      if (payload) req.write(payload);
      req.end();
    });
  }
}

module.exports = { ProviderAdapter };
