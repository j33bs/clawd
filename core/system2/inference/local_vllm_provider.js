'use strict';

const http = require('node:http');
const https = require('node:https');
const { URL } = require('node:url');
const { getProvider } = require('./catalog');

function normalizeBaseUrl(input) {
  const raw = String(input || '').trim();
  if (!raw) {
    return 'http://127.0.0.1:8001/v1';
  }
  const trimmed = raw.replace(/\/+$/, '');
  return /\/v1$/i.test(trimmed) ? trimmed : `${trimmed}/v1`;
}

class LocalVllmProvider {
  constructor(options = {}) {
    const env = options.env || process.env;
    this.entry = options.entry || getProvider('local_vllm');
    if (!this.entry) {
      throw new Error('local_vllm not found in catalog');
    }

    this.providerId = this.entry.provider_id;
    this.protocol = this.entry.protocol;
    this.baseUrl = normalizeBaseUrl(
      options.baseUrl
      || env.OPENCLAW_VLLM_BASE_URL
      || this.entry.base_url.default
    );
    this._authToken = options.apiKey || env.OPENCLAW_VLLM_API_KEY || null;
    const firstModel = this.entry.models[0];
    this._defaultModelId = firstModel ? firstModel.model_id : null;
  }

  async healthProbe() {
    const url = `${this.baseUrl}/models`;
    const data = await this._httpRequest('GET', url);
    const models = Array.isArray(data && data.data)
      ? data.data.map((m) => m.id).filter(Boolean)
      : [];
    return { ok: true, models };
  }

  async generateChat({ messages = [], options = {} }) {
    const model = options.model || this._defaultModelId;
    const maxTokens = options.maxTokens || options.max_tokens || 4096;
    const temperature = typeof options.temperature === 'number' ? options.temperature : 0.7;

    const payload = {
      model,
      messages,
      max_tokens: maxTokens,
      temperature,
      stream: false
    };

    const data = await this._httpRequest(
      'POST',
      `${this.baseUrl}/chat/completions`,
      payload
    );

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
        estimatedCostUsd: 0
      }
    };
  }

  async health() {
    try {
      return await this.healthProbe();
    } catch (error) {
      return { ok: false, reason: error.message };
    }
  }

  async call({ messages = [], metadata = {} }) {
    return this.generateChat({
      messages,
      options: metadata
    });
  }

  _buildHeaders() {
    const headers = { 'Content-Type': 'application/json' };
    if (this._authToken) {
      headers.Authorization = `Bearer ${this._authToken}`;
    }
    return headers;
  }

  _httpRequest(method, urlStr, body) {
    return new Promise((resolve, reject) => {
      const parsed = new URL(urlStr);
      const isHttps = parsed.protocol === 'https:';
      const mod = isHttps ? https : http;
      const payload = body ? JSON.stringify(body) : null;
      const headers = this._buildHeaders();
      if (payload) {
        headers['Content-Length'] = Buffer.byteLength(payload);
      }

      const req = mod.request({
        hostname: parsed.hostname,
        port: parsed.port || (isHttps ? 443 : 80),
        path: parsed.pathname + parsed.search,
        method,
        headers,
        timeout: 10000
      }, (res) => {
        let data = '';
        res.on('data', (chunk) => { data += chunk; });
        res.on('end', () => {
          if (res.statusCode >= 400) {
            return reject(new Error(`vllm_http_${res.statusCode}`));
          }
          try {
            resolve(JSON.parse(data));
          } catch (_) {
            reject(new Error(`invalid JSON from local_vllm: ${data.slice(0, 200)}`));
          }
        });
      });

      req.on('timeout', () => {
        req.destroy();
        reject(new Error('timeout connecting to local_vllm'));
      });
      req.on('error', (err) => reject(err));
      if (payload) req.write(payload);
      req.end();
    });
  }
}

module.exports = {
  LocalVllmProvider,
  normalizeBaseUrl
};
