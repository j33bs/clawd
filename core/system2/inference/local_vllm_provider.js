'use strict';

/**
 * LocalVllmProvider — GPU-native vLLM inference adapter.
 *
 * Key improvements over the original stub:
 *  1. **SSE streaming** via generateStream() — yields token chunks as they arrive.
 *  2. **JSON schema guided decoding** — forwards response_format to vLLM for
 *     GPU-level token filtering (zero invalid-JSON hallucination).
 *  3. **Native tool call pass-through** — sends tools/tool_choice through to the
 *     Hermes tool-call parser running inside vLLM (--tool-call-parser hermes flag).
 *  4. **Auto model discovery** — healthProbe() populates real model ID + context
 *     window from /v1/models; generateChat uses the discovered ID automatically.
 *  5. **Realistic timeouts** — generation timeout is 120 s (was 10 s); the 10 s
 *     limit was causing spurious failures on first tokens of long responses.
 *  6. **Structured error codes** — HTTP errors carry the status code in the thrown
 *     Error for the circuit breaker to classify (rate-limit vs server error).
 */

const http = require('node:http');
const https = require('node:https');
const { URL } = require('node:url');
const { getProvider } = require('./catalog');
const { enforceToolPayloadInvariant } = require('./tool_payload_sanitizer');

const FINAL_DISPATCH_TAG = 'gateway.adapter.final_dispatch';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function normalizeBaseUrl(input) {
  const raw = String(input || '').trim();
  if (!raw) return 'http://127.0.0.1:8001/v1';
  const trimmed = raw.replace(/\/+$/, '');
  return /\/v1$/i.test(trimmed) ? trimmed : `${trimmed}/v1`;
}

/** Build a shallow payload, omitting keys with undefined values. */
function compactAssign(target, source) {
  for (const [k, v] of Object.entries(source)) {
    if (v !== undefined) target[k] = v;
  }
  return target;
}

function toBool(value) {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'string') {
    return ['1', 'true', 'yes'].includes(value.toLowerCase());
  }
  return Boolean(value);
}

function hasTools(tools) {
  return Array.isArray(tools) && tools.length > 0;
}

function includesToolCallUnsupportedHint(text) {
  const value = String(text || '').toLowerCase();
  return value.includes('"auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set')
    || (
      value.includes('auto')
      && value.includes('tool choice')
      && value.includes('--enable-auto-tool-choice')
      && value.includes('--tool-call-parser')
    );
}

async function forwardGeneratedStream(stream, sink) {
  const target = sink || process.stdout;
  const donePayload = { usage: null, model: null, finishReason: null };
  for await (const chunk of stream) {
    if (!chunk || typeof chunk !== 'object') continue;
    if (chunk.type === 'delta') {
      if (target && typeof target.send === 'function') {
        target.send({ type: 'delta', text: chunk.text || '' });
      } else if (target && typeof target.write === 'function') {
        target.write(chunk.text || '');
      }
      continue;
    }
    if (chunk.type === 'done') {
      donePayload.usage = chunk.usage || null;
      donePayload.model = chunk.model || null;
      donePayload.finishReason = chunk.finishReason || null;
      if (target && typeof target.send === 'function') {
        target.send({ type: 'done', ...donePayload });
      }
    }
  }
  if (target && typeof target.end === 'function') target.end();
  if (target && typeof target.close === 'function') target.close();
  return donePayload;
}

// ---------------------------------------------------------------------------
// Provider class
// ---------------------------------------------------------------------------

class LocalVllmProvider {
  constructor(options = {}) {
    const env = options.env || process.env;
    this.entry = options.entry || getProvider('local_vllm');
    if (!this.entry) throw new Error('local_vllm not found in catalog');

    this.providerId   = this.entry.provider_id;
    this.protocol     = this.entry.protocol;
    this.baseUrl      = normalizeBaseUrl(
      options.baseUrl
      || env.OPENCLAW_VLLM_BASE_URL
      || this.entry.base_url.default
    );
    this._authToken   = options.apiKey || env.OPENCLAW_VLLM_API_KEY || null;

    const firstModel        = this.entry.models[0];
    this._defaultModelId    = firstModel ? firstModel.model_id : 'AUTO_DISCOVER';
    this._discoveredModelId = null;   // set by healthProbe()
    this._discoveredCtxLen  = null;   // set by healthProbe()
    const autoToolFlag = options.enableAutoToolChoice ?? env.OPENCLAW_VLLM_ENABLE_AUTO_TOOL_CHOICE;
    const parserFlag = env.OPENCLAW_VLLM_TOOL_CALL_PARSER;
    this._toolParserEnabled = toBool(autoToolFlag ?? parserFlag);
    this._toolCallEnabled = String(options.enableToolCall ?? env.OPENCLAW_VLLM_TOOLCALL ?? '0') === '1';
  }

  _toolChoiceAllowed(value) {
    if (value === undefined || value === 'none') return true;
    if (!this._toolParserEnabled) return false;
    return true;
  }

  _buildToolPayload(options) {
    if (!this._toolParserEnabled && !hasTools(options.tools)) {
      return {};
    }

    const payload = {};
    if (hasTools(options.tools) && this._toolParserEnabled) {
      payload.tools = options.tools;
    }

    const requested = options.tool_choice;
    if (this._toolChoiceAllowed(requested) && requested !== undefined) {
      payload.tool_choice = requested;
    } else if (this._toolParserEnabled && hasTools(options.tools) && requested === undefined) {
      payload.tool_choice = 'auto';
    }

    return payload;
  }

  _sanitizePayloadForToolCalls(payload) {
    const providerCaps = { tool_calls_supported: this._toolCallEnabled };
    const next = enforceToolPayloadInvariant(payload, providerCaps, {
      provider_id: this.providerId,
      model_id: payload && payload.model,
      callsite_tag: FINAL_DISPATCH_TAG
    });
    if (this._toolCallEnabled) return next;
    delete next.parallel_tool_calls;
    delete next.tool_calls;
    delete next.function_call;
    return next;
  }

  // -------------------------------------------------------------------------
  // Health + model discovery
  // -------------------------------------------------------------------------

  /**
   * Probe /v1/models, auto-discover the real model ID and context window.
   * Sets _discoveredModelId so subsequent generateChat calls use the right name.
   */
  async healthProbe() {
    const data   = await this._httpRequest('GET', `${this.baseUrl}/models`, null, { timeoutMs: 5000 });
    const models = Array.isArray(data && data.data) ? data.data : [];
    const ids    = models.map((m) => m.id).filter(Boolean);

    if (models.length > 0) {
      const first = models[0];
      this._discoveredModelId = first.id;
      // vLLM exposes max_model_len in the model object
      this._discoveredCtxLen  = first.max_model_len || null;
    }

    return { ok: true, models: ids, contextLen: this._discoveredCtxLen };
  }

  async health() {
    try { return await this.healthProbe(); }
    catch (err) { return { ok: false, reason: err.message }; }
  }

  // -------------------------------------------------------------------------
  // Model ID resolution
  // -------------------------------------------------------------------------

  _resolveModelId(requested) {
    if (requested && requested !== 'AUTO_DISCOVER') return requested;
    if (this._discoveredModelId)                   return this._discoveredModelId;
    return this._defaultModelId;
  }

  _resolveMaxTokens(requested) {
    const cap = this._discoveredCtxLen || 16384;
    return Math.min(requested || 4096, cap);
  }

  // -------------------------------------------------------------------------
  // Non-streaming chat completion
  // -------------------------------------------------------------------------

  /**
   * Generate a chat completion and return the full result.
   *
   * Extended options:
   *   model          — override model id
   *   maxTokens      — max completion tokens (capped at discovered ctx window)
   *   temperature    — sampling temperature
   *   response_format — { type: 'json_object' } or { type: 'json_schema', json_schema: {...} }
   *                     Forwarded verbatim → vLLM guided decoding.
   *   tools          — OpenAI-format tool definitions (Hermes parser handles them).
   *   tool_choice    — 'auto' | 'none' | { type: 'function', function: { name } }
   *   stop           — stop sequences
   *   top_p          — nucleus sampling
   */
  async generateChat({ messages = [], options = {} }) {
    const model     = this._resolveModelId(options.model);
    const maxTokens = this._resolveMaxTokens(options.maxTokens || options.max_tokens);
    const temp      = typeof options.temperature === 'number' ? options.temperature : 0.7;

    const payload = this._sanitizePayloadForToolCalls(compactAssign(
      { model, messages, max_tokens: maxTokens, temperature: temp, stream: false },
      this._buildToolPayload(options),
      {
        response_format: options.response_format,
        stop:            options.stop,
        top_p:           options.top_p,
      }
    ));

    const data   = await this._httpRequest('POST', `${this.baseUrl}/chat/completions`, payload, { timeoutMs: 120000 });
    const choice = (data.choices && data.choices[0]) || {};
    const msg    = choice.message || {};
    const usage  = data.usage || {};

    return {
      text:       msg.content || '',
      toolCalls:  msg.tool_calls || null,
      finishReason: choice.finish_reason || null,
      model:      data.model || model,
      raw:        data,
      usage: {
        inputTokens:      usage.prompt_tokens     || 0,
        outputTokens:     usage.completion_tokens || 0,
        totalTokens:      usage.total_tokens      || 0,
        estimatedCostUsd: 0,
      },
    };
  }

  // -------------------------------------------------------------------------
  // Streaming chat completion (SSE)
  // -------------------------------------------------------------------------

  /**
   * Streaming variant.  Returns an async generator that yields objects:
   *
   *   { type: 'delta', text: string }        — partial content token(s)
   *   { type: 'tool_call_delta', raw: obj }  — partial tool call chunk
   *   { type: 'done', usage: obj, model: string, finishReason: string }
   *
   * Usage:
   *   for await (const chunk of provider.generateStream({ messages, options })) {
   *     if (chunk.type === 'delta') process.stdout.write(chunk.text);
   *   }
   */
  async *generateStream({ messages = [], options = {} }) {
    const model     = this._resolveModelId(options.model);
    const maxTokens = this._resolveMaxTokens(options.maxTokens || options.max_tokens);
    const temp      = typeof options.temperature === 'number' ? options.temperature : 0.7;

    const payload = this._sanitizePayloadForToolCalls(compactAssign(
      { model, messages, max_tokens: maxTokens, temperature: temp, stream: true },
      this._buildToolPayload(options),
      {
        response_format:    options.response_format,
        stop:               options.stop,
        top_p:              options.top_p,
        stream_options:     { include_usage: true },
      }
    ));

    yield* this._streamRequest(`${this.baseUrl}/chat/completions`, payload);
  }

  async generateChatStreamProxy({ messages = [], options = {}, sink = null }) {
    return forwardGeneratedStream(this.generateStream({ messages, options }), sink);
  }

  // -------------------------------------------------------------------------
  // Unified call() interface (non-streaming)
  // -------------------------------------------------------------------------

  async call({ messages = [], metadata = {} }) {
    return this.generateChat({ messages, options: metadata });
  }

  // -------------------------------------------------------------------------
  // HTTP primitives
  // -------------------------------------------------------------------------

  _buildHeaders(hasBody) {
    const headers = { 'Content-Type': 'application/json' };
    if (this._authToken) headers['Authorization'] = `Bearer ${this._authToken}`;
    return headers;
  }

  /** Single-shot JSON request (GET or POST). */
  _httpRequest(method, urlStr, body, { timeoutMs = 10000 } = {}) {
    return new Promise((resolve, reject) => {
      const parsed  = new URL(urlStr);
      const isHttps = parsed.protocol === 'https:';
      const mod     = isHttps ? https : http;
      const payload = body ? JSON.stringify(body) : null;
      const headers = this._buildHeaders(!!payload);
      if (payload) headers['Content-Length'] = Buffer.byteLength(payload);

      const req = mod.request({
        hostname: parsed.hostname,
        port:     parsed.port || (isHttps ? 443 : 80),
        path:     parsed.pathname + parsed.search,
        method,
        headers,
        timeout:  timeoutMs,
      }, (res) => {
        let data = '';
        res.on('data', (chunk) => { data += chunk; });
        res.on('end', () => {
          if (res.statusCode >= 400) {
            if (includesToolCallUnsupportedHint(data)) {
              const err = new Error(
                'vLLM tool-calling unsupported for this server configuration. ' +
                'Start vLLM with --enable-auto-tool-choice --tool-call-parser … OR set OPENCLAW_VLLM_TOOLCALL=0 (default).'
              );
              err.code = 'PROVIDER_TOOLCALL_UNSUPPORTED';
              err.statusCode = res.statusCode;
              return reject(err);
            }
            const err = new Error(`vllm_http_${res.statusCode}`);
            err.code = 'PROVIDER_HTTP_ERROR';
            err.statusCode = res.statusCode;
            return reject(err);
          }
          try   { resolve(JSON.parse(data)); }
          catch { reject(new Error(`invalid JSON from local_vllm: ${data.slice(0, 300)}`)); }
        });
      });

      req.on('timeout', () => { req.destroy(); reject(new Error('timeout connecting to local_vllm')); });
      req.on('error',   (err) => reject(err));
      if (payload) req.write(payload);
      req.end();
    });
  }

  /**
   * SSE streaming request — async generator over parsed `data:` lines.
   * Handles vLLM's `data: [DONE]` terminator and `data: {...}` JSON chunks.
   */
  async *_streamRequest(urlStr, body) {
    const parsed  = new URL(urlStr);
    const isHttps = parsed.protocol === 'https:';
    const mod     = isHttps ? https : http;
    const payload = JSON.stringify(body);
    const headers = this._buildHeaders(true);
    headers['Content-Length'] = Buffer.byteLength(payload);
    headers['Accept']         = 'text/event-stream';

    // We need a manually controlled async iterable so we can push chunks from
    // the Node.js stream into an async generator.  Use a queue + Promise gate.
    const queue   = [];
    let   resolve = null;
    let   done    = false;
    let   error   = null;

    function push(item) {
      queue.push(item);
      if (resolve) { const r = resolve; resolve = null; r(); }
    }
    function finish(err) {
      error = err || null;
      done  = true;
      if (resolve) { const r = resolve; resolve = null; r(); }
    }

    const req = mod.request({
      hostname: parsed.hostname,
      port:     parsed.port || (isHttps ? 443 : 80),
      path:     parsed.pathname + parsed.search,
      method:   'POST',
      headers,
      timeout:  120000,
    }, (res) => {
      if (res.statusCode >= 400) {
        let errBody = '';
        res.on('data', (chunk) => { errBody += chunk.toString(); });
        res.on('end', () => {
          if (includesToolCallUnsupportedHint(errBody)) {
            const err = new Error(
              'vLLM tool-calling unsupported for this server configuration. ' +
              'Start vLLM with --enable-auto-tool-choice --tool-call-parser … OR set OPENCLAW_VLLM_TOOLCALL=0 (default).'
            );
            err.code = 'PROVIDER_TOOLCALL_UNSUPPORTED';
            err.statusCode = res.statusCode;
            finish(err);
            return;
          }
          const err = new Error(`vllm_stream_http_${res.statusCode}`);
          err.code = 'PROVIDER_HTTP_ERROR';
          err.statusCode = res.statusCode;
          finish(err);
        });
        res.on('error', (err) => finish(err));
        return;
      }

      let buf = '';
      res.on('data', (chunk) => {
        buf += chunk.toString();
        const lines = buf.split('\n');
        buf = lines.pop(); // last partial line stays in buf

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || trimmed === ':') continue; // SSE keep-alive
          if (!trimmed.startsWith('data:')) continue;

          const json = trimmed.slice(5).trim();
          if (json === '[DONE]') continue; // handled by 'end'

          let obj;
          try   { obj = JSON.parse(json); }
          catch { continue; }

          const choice     = (obj.choices && obj.choices[0]) || {};
          const delta      = choice.delta || {};
          const finishReason = choice.finish_reason;
          const usage      = obj.usage || null;

          if (delta.content) {
            push({ type: 'delta', text: delta.content });
          }
          if (delta.tool_calls) {
            push({ type: 'tool_call_delta', raw: delta.tool_calls });
          }
          if (finishReason || usage) {
            push({ type: 'done', finishReason: finishReason || null, usage, model: obj.model });
          }
        }
      });

      res.on('end',   () => finish(null));
      res.on('error', (err) => finish(err));
    });

    req.on('timeout', () => { req.destroy(); finish(new Error('stream_timeout')); });
    req.on('error',   (err) => finish(err));
    req.write(payload);
    req.end();

    // Drain the queue via async iteration
    while (true) {
      if (queue.length > 0) {
        yield queue.shift();
        continue;
      }
      if (done) break;
      await new Promise((res) => { resolve = res; });
      if (error) throw error;
    }
    // Flush any remaining items
    while (queue.length > 0) yield queue.shift();
  }
}

module.exports = { LocalVllmProvider, normalizeBaseUrl, forwardGeneratedStream };
