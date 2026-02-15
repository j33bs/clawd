'use strict';

/**
 * FreeComputeCloud — Provider Registry
 *
 * Manages the lifecycle of provider adapters: construction,
 * health tracking, circuit breaker integration, and disposal.
 *
 * This is the main entry point for the inference layer.
 * Feature flag: does nothing when ENABLE_FREECOMPUTE_CLOUD=0.
 */

const { CATALOG } = require('./catalog');
const { ProviderAdapter } = require('./provider_adapter');
const { loadFreeComputeConfig } = require('./config');
const { SecretsBridge } = require('./secrets_bridge');
const { QuotaLedger } = require('./quota_ledger');
const { routeRequest, explainRouting } = require('./router');

const CB_STATES = Object.freeze({
  CLOSED: 'CLOSED',
  OPEN: 'OPEN',
  HALF_OPEN: 'HALF_OPEN'
});

const COMPACTION_MARKER = '[TRUNCATED FOR SIZE]';
const COMPACTION_NOTE = '(Context compacted due to provider limits.)';

function classifyDispatchError(err) {
  const code = err && err.code;
  const msg = String((err && err.message) || '');
  if (code === 'PROVIDER_TIMEOUT' || code === 'ETIMEDOUT' || /timeout/i.test(msg)) {
    return 'timeout';
  }
  if (code === 'PROVIDER_HTTP_ERROR' && typeof err.statusCode === 'number') {
    if (err.statusCode === 429) return 'rate_limit';
    if (err.statusCode === 401 || err.statusCode === 403) return 'auth';
    if (err.statusCode === 400 || err.statusCode === 404) return 'config';
    return 'http_error';
  }
  return 'unknown';
}

function hasAuthCredential(auth, env) {
  if (!auth || auth.type === 'none' || auth.type === 'bearer_optional') return true;
  const primary = auth.env_var;
  const aliases = Array.isArray(auth.alias_env_vars) ? auth.alias_env_vars : [];
  if (primary && env[primary]) return true;
  for (const k of aliases) {
    if (k && env[k]) return true;
  }
  return false;
}

function _safeTextLen(v) {
  return typeof v === 'string' ? v.length : 0;
}

function estimateRequestShape(messages) {
  const out = {
    messages_count: 0,
    char_count_total: 0,
    system_chars: 0,
    user_chars: 0,
    assistant_chars: 0
  };

  if (!Array.isArray(messages)) return out;

  for (const m of messages) {
    if (!m || typeof m !== 'object') continue;
    const role = typeof m.role === 'string' ? m.role : '';
    let contentChars = 0;

    const c = m.content;
    if (typeof c === 'string') {
      contentChars += c.length;
    } else if (Array.isArray(c)) {
      for (const part of c) {
        if (typeof part === 'string') {
          contentChars += part.length;
        } else if (part && typeof part === 'object' && typeof part.text === 'string') {
          contentChars += part.text.length;
        }
      }
    }

    // Small deterministic overhead so "nearly identical" payloads compare consistently.
    const overhead = 8 + role.length;

    out.messages_count += 1;
    out.char_count_total += contentChars + overhead;
    if (role === 'system') out.system_chars += contentChars;
    if (role === 'user') out.user_chars += contentChars;
    if (role === 'assistant') out.assistant_chars += contentChars;
  }

  return out;
}

function sanitizeModelIdForEnv(modelId) {
  return String(modelId || '')
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
}

function resolveMaxChars({ env, provider_id, model_id, taskClass }) {
  const e = env || {};
  const globalDefault = Number(e.DEFAULT_MAX_CHARS || 24000);

  // Per-model override wins.
  const provKey = String(provider_id || '').toUpperCase().replace(/[^A-Z0-9]+/g, '_');
  const modelKey = sanitizeModelIdForEnv(model_id);
  if (provKey && modelKey) {
    const perModel = `OPENCLAW_MAX_CHARS__${provKey}__${modelKey}`;
    const v = Number(e[perModel]);
    if (Number.isFinite(v) && v > 0) return v;
  }

  // Provider defaults with env overrides.
  if (provider_id === 'groq') {
    const v = Number(e.GROQ_MAX_CHARS);
    if (Number.isFinite(v) && v > 0) return v;
    return globalDefault;
  }

  if (provider_id === 'local_vllm' || provider_id === 'ollama') {
    const v = Number(e.LOCAL_MAX_CHARS);
    if (Number.isFinite(v) && v > 0) return v;
    return Number(e.LOCAL_DEFAULT_MAX_CHARS || 32000) || 32000;
  }

  // Future providers: fall back to global default.
  void taskClass;
  return globalDefault;
}

function isLikelyRequestTooLargeError(err) {
  const sc = err && typeof err.statusCode === 'number' ? err.statusCode : null;
  if (sc !== 400 && sc !== 413) return false;
  const msg = String((err && err.message) || '');
  return /context|too large|token|length|reduce the length/i.test(msg);
}

function _truncateString(s, maxLen) {
  if (typeof s !== 'string') return s;
  if (s.length <= maxLen) return s;
  const marker = COMPACTION_MARKER;
  const keep = Math.max(0, maxLen - (marker.length + 1));
  const head = s.slice(0, keep);
  return `${head} ${marker}`.trim();
}

function _truncateMessageContent(content, maxLen) {
  if (typeof content === 'string') return _truncateString(content, maxLen);

  if (Array.isArray(content)) {
    const next = [];
    let remaining = maxLen;
    for (const part of content) {
      if (remaining <= 0) break;
      if (typeof part === 'string') {
        const t = _truncateString(part, remaining);
        next.push(t);
        remaining -= _safeTextLen(t);
        continue;
      }
      if (part && typeof part === 'object' && typeof part.text === 'string') {
        const t = _truncateString(part.text, remaining);
        next.push({ ...part, text: t });
        remaining -= _safeTextLen(t);
        continue;
      }
      // Keep non-text parts unchanged (but they don't count toward our chars budget).
      next.push(part);
    }
    return next;
  }

  return content;
}

function _truncateMessageToTotalBudget(message, totalBudget) {
  const role = message && typeof message.role === 'string' ? message.role : '';
  const overhead = 8 + role.length;
  const budget = Math.max(0, Number(totalBudget) || 0);
  const maxContent = Math.max(0, budget - overhead);

  // If we can't fit any content, preserve only structure.
  if (maxContent <= 0) {
    if (Array.isArray(message.content)) return { ...message, content: [] };
    if (typeof message.content === 'string') return { ...message, content: '' };
    return { ...message };
  }

  return { ...message, content: _truncateMessageContent(message.content, maxContent) };
}

function compactMessagesForBudget(messages, targetChars) {
  const before = estimateRequestShape(messages);
  if (!Array.isArray(messages) || messages.length === 0) {
    return { messages: Array.isArray(messages) ? messages : [], before, after: before };
  }

  const target = Math.max(0, Number(targetChars) || 0);
  if (target <= 0) {
    return { messages: [], before, after: estimateRequestShape([]) };
  }

  // Decide which indices to keep; replacements holds truncated message objects.
  const keep = new Set();
  const replacements = new Map();

  // System budget: keep early system messages up to a cap.
  const systemBudget = Math.min(6000, Math.floor(target * 0.35));
  let usedSystem = 0;

  for (let i = 0; i < messages.length; i++) {
    const m = messages[i];
    if (!m || m.role !== 'system') continue;
    const c = m.content;
    const msgChars = estimateRequestShape([m]).char_count_total;
    if (usedSystem + msgChars <= systemBudget) {
      keep.add(i);
      usedSystem += msgChars;
      continue;
    }
    const remaining = Math.max(0, systemBudget - usedSystem);
    if (remaining > 0) {
      keep.add(i);
      replacements.set(i, _truncateMessageToTotalBudget({ ...m, content: c }, remaining));
      usedSystem = systemBudget;
    }
    break;
  }

  // Tail budget: keep the newest messages, ensuring the latest user message survives if possible.
  let latestUserIdx = -1;
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m && m.role === 'user') {
      latestUserIdx = i;
      break;
    }
  }

  const mustKeep = new Set();
  if (latestUserIdx >= 0) mustKeep.add(latestUserIdx);
  mustKeep.add(messages.length - 1);

  // Reserve a small note; we only apply it if we have a system message kept.
  const noteCost = COMPACTION_NOTE.length + 2;
  let remainingBudget = Math.max(0, target - usedSystem - noteCost);

  for (let i = messages.length - 1; i >= 0; i--) {
    if (keep.has(i)) continue;
    const m = messages[i];
    if (!m || typeof m !== 'object') continue;
    if (m.role === 'system') continue;

    const msgChars = estimateRequestShape([m]).char_count_total;
    if (msgChars <= remainingBudget) {
      keep.add(i);
      remainingBudget -= msgChars;
      continue;
    }

    if (mustKeep.has(i) && remainingBudget > 0) {
      keep.add(i);
      replacements.set(i, _truncateMessageToTotalBudget(m, remainingBudget));
      remainingBudget = 0;
      continue;
    }
  }

  // Apply note by appending to the last kept system message if there is room.
  const keptSystemIndices = Array.from(keep).filter((i) => messages[i] && messages[i].role === 'system').sort((a, b) => a - b);
  if (keptSystemIndices.length > 0) {
    const i = keptSystemIndices[keptSystemIndices.length - 1];
    const base = replacements.get(i) || messages[i];
    const content = typeof base.content === 'string' ? base.content : null;
    if (content !== null) {
      const next = `${content}\n${COMPACTION_NOTE}`;
      // Only append if it doesn't exceed the system budget cap by much.
      if (next.length <= (systemBudget + 200)) {
        replacements.set(i, { ...base, content: next });
      }
    }
  }

  // Emit compacted messages in original order; never reorder.
  const out = [];
  for (let i = 0; i < messages.length; i++) {
    if (!keep.has(i)) continue;
    const m = replacements.get(i) || messages[i];
    out.push(m);
  }

  const after = estimateRequestShape(out);
  return { messages: out, before, after };
}

class ProviderRegistry {
  /**
   * @param {object} [options]
   * @param {object} [options.env]       - Environment variables
   * @param {function} [options.emitEvent] - (eventType, payload) => void
   * @param {object} [options.configOverride] - Override loadFreeComputeConfig()
   */
  constructor(options = {}) {
    // Fail-closed: never mutate the caller's env object or process.env.
    // We always operate on a shallow clone ("effective env") so secrets injection
    // is scoped to this registry instance.
    const baseEnv = options.env || process.env;
    this._env = { ...baseEnv };
    this._emitEvent = options.emitEvent || (() => {});
    this.config = options.configOverride || loadFreeComputeConfig(this._env);
    this._secretsBridge = null;

    this._adapters = new Map();       // provider_id → ProviderAdapter
    this._health = new Map();         // provider_id → { ok, reason, checkedAt }
    this._circuitBreakers = new Map(); // provider_id → { state, failures, openedAt }
    this._localGenerationProbe = { ok: null, reason: null, checkedAt: 0 };

    this.ledger = new QuotaLedger({
      ledgerPath: this.config.ledger.path,
      resetHour: this.config.ledger.resetHour,
      disabled: !this.config.enabled
    });

    if (this.config.secretsBridge && this.config.secretsBridge.enabled) {
      this._secretsBridge = new SecretsBridge({ env: this._env });
      try {
        const injection = this._secretsBridge.injectRuntimeEnv(this._env);
        this._emitEvent('freecompute_secrets_bridge_injection', {
          backend: injection.backend,
          injected_count: injection.injected.length,
          skipped_count: injection.skipped.length
        });
      } catch (error) {
        this._emitEvent('freecompute_secrets_bridge_error', {
          error: error.message
        });
      }
    }

    // Always initialize adapters so local vLLM can act as an escape hatch even
    // when FreeComputeCloud (cloud/free tiers) is disabled.
    this._initAdapters();
  }

  /**
   * Execute a request through the routing + adapter pipeline.
   *
   * @param {object} params
   * @param {string} params.taskClass
   * @param {Array}  params.messages
   * @param {object} [params.metadata]
   * @param {number} [params.contextLength]
   * @param {string} [params.latencyTarget]
   * @param {object} [params.budget]
   * @returns {Promise<{ text, raw, usage, provider_id, model_id } | null>}
   */
  async dispatch(params) {
    // Cloud/free tiers are gated behind ENABLE_FREECOMPUTE_CLOUD (or alias),
    // but local vLLM can still serve requests when ENABLE_LOCAL_VLLM!=0.
    if (!this.config.enabled && !this.config.vllmEnabled) {
      return null;
    }

    // Refresh local vLLM generation probe (deterministic, cached).
    await this._ensureLocalVllmGenerationProbe();

    // Build health and quota state for routing
    const providerHealth = {};
    const quotaState = {};

    for (const [pid] of this._adapters) {
      providerHealth[pid] = this._health.get(pid) || { ok: true };

      // Circuit breaker check
      const cb = this._circuitBreakers.get(pid);
      if (cb && cb.state === CB_STATES.OPEN) {
        const entry = CATALOG.find((e) => e.provider_id === pid);
        const cooldown = (entry && entry.constraints.circuit_breaker.open_seconds || 120) * 1000;
        if (Date.now() - cb.openedAt < cooldown) {
          providerHealth[pid] = { ok: false, reason: 'circuit_open' };
        } else {
          cb.state = CB_STATES.HALF_OPEN;
        }
      }

      // Quota check
      const entry = CATALOG.find((e) => e.provider_id === pid);
      if (entry && entry.constraints.quota) {
        const q = entry.constraints.quota;
        const caps = {
          rpm: q.rpm_default,
          rpd: q.rpd_default,
          tpm: q.tpm_default,
          tpd: q.tpd_default
        };
        quotaState[pid] = this.ledger.check(pid, caps);
      } else {
        quotaState[pid] = { allowed: true };
      }
    }

    // Route
    const { candidates } = routeRequest({
      taskClass: params.taskClass,
      contextLength: params.contextLength,
      latencyTarget: params.latencyTarget,
      budget: params.budget,
      providerHealth,
      quotaState,
      config: this.config,
      availableProviderIds: Array.from(this._adapters.keys())
    });

    if (candidates.length === 0) {
      this._emitEvent('freecompute_no_candidates', {
        taskClass: params.taskClass
      });
      return null;
    }

    const attemptSummaries = [];

    // Try candidates in order
    for (const candidate of candidates) {
      const adapter = this._adapters.get(candidate.provider_id);
      if (!adapter) continue;

      const baseCallParams = {
        messages: params.messages,
        metadata: {
          model: candidate.model_id,
          ...(params.metadata || {})
        }
      };

      const maxChars = resolveMaxChars({
        env: this._env,
        provider_id: candidate.provider_id,
        model_id: candidate.model_id,
        taskClass: params.taskClass
      });

      const preShape = estimateRequestShape(baseCallParams.messages);
      let callParams = baseCallParams;
      let compactedOnce = false;

      // Preflight compaction only when materially over budget (avoid overcompaction).
      if (preShape.char_count_total > Math.floor(maxChars * 1.05)) {
        const target = Math.floor(maxChars * 0.9);
        const compacted = compactMessagesForBudget(baseCallParams.messages, target);
        callParams = { ...baseCallParams, messages: compacted.messages };
        compactedOnce = true;
        this._emitEvent('freecompute_dispatch_compaction_applied', {
          provider_id: candidate.provider_id,
          model_id: candidate.model_id,
          trigger: 'preflight',
          before_chars: compacted.before.char_count_total,
          after_chars: compacted.after.char_count_total,
          messages_before: compacted.before.messages_count,
          messages_after: compacted.after.messages_count
        });
      }

      let timeoutRetries = 0;
      let sizeRetry = 0;
      const maxTimeoutRetries = 1;
      const maxSizeRetries = 1;

      while (true) {
        const shape = estimateRequestShape(callParams.messages);
        this._emitEvent('freecompute_dispatch_request_shape', {
          provider_id: candidate.provider_id,
          model_id: candidate.model_id,
          messages_count: shape.messages_count,
          char_count_total: shape.char_count_total,
          system_chars: shape.system_chars,
          user_chars: shape.user_chars,
          assistant_chars: shape.assistant_chars
        });

        try {
          const result = await adapter.call(callParams);
          const resolvedModelId = result.model || candidate.model_id;

          // Record success
          this.ledger.record(candidate.provider_id, {
            tokensIn: result.usage.inputTokens,
            tokensOut: result.usage.outputTokens
          });
          this._recordCbSuccess(candidate.provider_id);

          this._emitEvent('freecompute_dispatch', {
            provider_id: candidate.provider_id,
            model_id: resolvedModelId,
            tokens_in: result.usage.inputTokens,
            tokens_out: result.usage.outputTokens,
            ok: true
          });

          return {
            ...result,
            provider_id: candidate.provider_id,
            model_id: resolvedModelId
          };
        } catch (err) {
          const kind = classifyDispatchError(err);
          this._recordCbFailure(candidate.provider_id, kind);

          const shapeAfterErr = estimateRequestShape(callParams.messages);
          attemptSummaries.push({
            provider_id: candidate.provider_id,
            model_id: candidate.model_id,
            kind,
            statusCode: typeof err.statusCode === 'number' ? err.statusCode : null,
            char_count_total: shapeAfterErr.char_count_total,
            messages_count: shapeAfterErr.messages_count
          });

          this._emitEvent('freecompute_dispatch_error', {
            provider_id: candidate.provider_id,
            model_id: candidate.model_id,
            error: err.message
          });

          this._emitEvent('freecompute_dispatch_error_shape', {
            provider_id: candidate.provider_id,
            model_id: candidate.model_id,
            statusCode: typeof err.statusCode === 'number' ? err.statusCode : null,
            err_code: err && err.code ? String(err.code) : null,
            err_kind: kind,
            messages_count: shapeAfterErr.messages_count,
            char_count_total: shapeAfterErr.char_count_total
          });

          // Retry timeouts at most once per provider per request.
          if (kind === 'timeout' && timeoutRetries < maxTimeoutRetries) {
            timeoutRetries += 1;
            continue;
          }

          // Retry once with compacted context for likely "request too large" errors.
          if (sizeRetry < maxSizeRetries && isLikelyRequestTooLargeError(err) && !compactedOnce) {
            sizeRetry += 1;
            const target = Math.floor(maxChars * 0.9);
            const compacted = compactMessagesForBudget(callParams.messages, target);
            callParams = { ...callParams, messages: compacted.messages };
            compactedOnce = true;
            const sc = typeof err.statusCode === 'number' ? err.statusCode : 400;
            const trigger = sc === 413 ? 'error_413' : 'error_400';
            this._emitEvent('freecompute_dispatch_compaction_applied', {
              provider_id: candidate.provider_id,
              model_id: candidate.model_id,
              trigger,
              before_chars: compacted.before.char_count_total,
              after_chars: compacted.after.char_count_total,
              messages_before: compacted.before.messages_count,
              messages_after: compacted.after.messages_count
            });
            continue;
          }

          // Try next candidate
          break;
        }
      }
    }

    this._emitEvent('freecompute_all_candidates_failed', {
      taskClass: params.taskClass,
      attempts: attemptSummaries
    });

    return null; // All candidates exhausted
  }

  /**
   * Run health checks on all registered adapters.
   * @returns {Promise<object>} { provider_id → { ok, reason?, models? } }
   */
  async healthCheckAll() {
    const results = {};
    for (const [pid, adapter] of this._adapters) {
      try {
        const h = await adapter.health();
        this._health.set(pid, { ...h, checkedAt: Date.now() });
        results[pid] = h;
      } catch (err) {
        const h = { ok: false, reason: err.message, checkedAt: Date.now() };
        this._health.set(pid, h);
        results[pid] = h;
      }
    }
    return results;
  }

  /**
   * Explain routing for a given request (diagnostic).
   */
  explain(params) {
    const providerHealth = {};
    const quotaState = {};
    for (const [pid] of this._adapters) {
      providerHealth[pid] = this._health.get(pid) || { ok: true };
      const entry = CATALOG.find((e) => e.provider_id === pid);
      if (entry && entry.constraints.quota) {
        const q = entry.constraints.quota;
        quotaState[pid] = this.ledger.check(pid, {
          rpm: q.rpm_default, rpd: q.rpd_default,
          tpm: q.tpm_default, tpd: q.tpd_default
        });
      } else {
        quotaState[pid] = { allowed: true };
      }
    }

    return explainRouting({
      ...params,
      providerHealth,
      quotaState,
      config: this.config,
      availableProviderIds: Array.from(this._adapters.keys())
    });
  }

  /**
   * Get a snapshot of the registry state for diagnostics.
   */
  snapshot() {
    const adapters = [];
    for (const [pid] of this._adapters) {
      const h = this._health.get(pid);
      const cb = this._circuitBreakers.get(pid);
      adapters.push({
        provider_id: pid,
        health: h || null,
        circuit_breaker: cb ? { state: cb.state, failures: cb.failures } : null
      });
    }
    return {
      enabled: this.config.enabled,
      adapters,
      quota: this.ledger.snapshot()
    };
  }

  dispose() {
    this._adapters.clear();
    this._health.clear();
    this._circuitBreakers.clear();
  }

  // ── Internal ────────────────────────────────────────────────────────

  _initAdapters() {
    for (const entry of CATALOG) {
      const pid = entry.provider_id;

      // Operator policy: OpenAI/Codex API automation is disabled for now.
      if (pid.startsWith('openai')) continue;

      // Skip local_vllm unless explicitly enabled
      if (pid === 'local_vllm' && !this.config.vllmEnabled) continue;

      // When cloud/free tiers are disabled, do not instantiate external providers.
      if (entry.kind === 'external' && !this.config.enabled) continue;

      // Skip external unless in allowlist (if allowlist is set) or not in denylist
      if (entry.kind === 'external') {
        if (this.config.providerAllowlist.length > 0 && !this.config.providerAllowlist.includes(pid)) continue;
        if (this.config.providerDenylist.includes(pid)) continue;
      }

      // remote_vllm: require explicit base URL configuration (no default networking).
      if (pid === 'remote_vllm') {
        const baseUrlKey = entry.base_url && entry.base_url.env_override;
        const baseUrl = baseUrlKey ? this._env[baseUrlKey] : null;
        if (!baseUrl) continue;
      }

      // Check if auth credential is available for providers that require it
      const authType = entry.auth && entry.auth.type;
      const requiresCredential = Boolean(authType && authType !== 'none' && authType !== 'bearer_optional');
      if (requiresCredential && !hasAuthCredential(entry.auth, this._env)) {
        // Skip providers without configured credentials
        continue;
      }

      this._adapters.set(pid, new ProviderAdapter(entry, {
        env: this._env,
        emitEvent: this._emitEvent
      }));

      this._circuitBreakers.set(pid, {
        state: CB_STATES.CLOSED,
        failures: 0,
        timeoutFailures: 0,
        openedAt: 0
      });
    }
  }

  async _ensureLocalVllmGenerationProbe() {
    const adapter = this._adapters.get('local_vllm');
    if (!adapter || typeof adapter.generationProbe !== 'function') {
      return { ok: true, reason: null };
    }

    const now = Date.now();
    const ttlMs = 60 * 1000;
    if (this._localGenerationProbe.checkedAt && (now - this._localGenerationProbe.checkedAt) < ttlMs) {
      // Keep existing cached health decision.
      return { ok: Boolean(this._localGenerationProbe.ok), reason: this._localGenerationProbe.reason };
    }

    // Short probe to detect "HTTP alive but generation wedged" failures.
    const timeoutMs = Number(this._env.FREECOMPUTE_LOCAL_VLLM_PROBE_TIMEOUT_MS || 5000);
    const result = await adapter.generationProbe({ timeoutMs });

    this._localGenerationProbe = {
      ok: Boolean(result && result.ok),
      reason: (result && result.reason) || null,
      checkedAt: now
    };

    if (this._localGenerationProbe.ok) {
      this._health.set('local_vllm', { ok: true, checkedAt: now });
    } else {
      const sub = this._localGenerationProbe.reason ? `:${this._localGenerationProbe.reason}` : '';
      this._health.set('local_vllm', { ok: false, reason: `generation_probe_failed${sub}`, checkedAt: now });
    }

    return { ok: this._localGenerationProbe.ok, reason: this._localGenerationProbe.reason };
  }

  _recordCbSuccess(providerId) {
    const cb = this._circuitBreakers.get(providerId);
    if (!cb) return;
    cb.failures = 0;
    cb.timeoutFailures = 0;
    if (cb.state === CB_STATES.HALF_OPEN) {
      cb.state = CB_STATES.CLOSED;
    }
  }

  _recordCbFailure(providerId, kind) {
    const cb = this._circuitBreakers.get(providerId);
    if (!cb) return;
    cb.failures += 1;

    const entry = CATALOG.find((e) => e.provider_id === providerId);
    const threshold = (entry && entry.constraints.circuit_breaker.consecutive_failures_to_open) || 3;

    if (kind === 'rate_limit') {
      cb.state = CB_STATES.OPEN;
      cb.openedAt = Date.now();
      return;
    }

    if (kind === 'timeout') {
      cb.timeoutFailures += 1;
      if (cb.timeoutFailures >= 2) {
        cb.state = CB_STATES.OPEN;
        cb.openedAt = Date.now();
        return;
      }
    } else {
      cb.timeoutFailures = 0;
    }

    if (kind === 'auth' || kind === 'config') {
      cb.state = CB_STATES.OPEN;
      cb.openedAt = Date.now();
      return;
    }

    if (cb.state === CB_STATES.HALF_OPEN || cb.failures >= threshold) {
      cb.state = CB_STATES.OPEN;
      cb.openedAt = Date.now();
    }
  }
}

module.exports = {
  ProviderRegistry,
  CB_STATES,
  _test: {
    classifyDispatchError,
    estimateRequestShape,
    resolveMaxChars,
    compactMessagesForBudget,
    isLikelyRequestTooLargeError
  }
};
