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

function classifyDispatchError(err) {
  const code = err && err.code;
  const msg = String((err && err.message) || '');
  if (code === 'PROVIDER_TIMEOUT' || code === 'ETIMEDOUT' || /timeout/i.test(msg)) {
    return 'timeout';
  }
  if (code === 'PROVIDER_HTTP_ERROR' && typeof err.statusCode === 'number') {
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

class ProviderRegistry {
  /**
   * @param {object} [options]
   * @param {object} [options.env]       - Environment variables
   * @param {function} [options.emitEvent] - (eventType, payload) => void
   * @param {object} [options.configOverride] - Override loadFreeComputeConfig()
   */
  constructor(options = {}) {
    this._env = options.env || process.env;
    this._emitEvent = options.emitEvent || (() => {});
    this.config = options.configOverride || loadFreeComputeConfig(this._env);
    this._secretsBridge = null;

    this._adapters = new Map();       // provider_id → ProviderAdapter
    this._health = new Map();         // provider_id → { ok, reason, checkedAt }
    this._circuitBreakers = new Map(); // provider_id → { state, failures, openedAt }

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

    if (this.config.enabled) {
      this._initAdapters();
    }
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
    if (!this.config.enabled) {
      return null;
    }

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
      config: this.config
    });

    if (candidates.length === 0) {
      this._emitEvent('freecompute_no_candidates', {
        taskClass: params.taskClass
      });
      return null;
    }

    // Try candidates in order
    for (const candidate of candidates) {
      const adapter = this._adapters.get(candidate.provider_id);
      if (!adapter) continue;

      const callParams = {
        messages: params.messages,
        metadata: {
          model: candidate.model_id,
          ...(params.metadata || {})
        }
      };

      let attempt = 0;
      const maxTimeoutRetries = 1;

      while (true) {
        try {
          const result = await adapter.call(callParams);

          // Record success
          this.ledger.record(candidate.provider_id, {
            tokensIn: result.usage.inputTokens,
            tokensOut: result.usage.outputTokens
          });
          this._recordCbSuccess(candidate.provider_id);

          this._emitEvent('freecompute_dispatch', {
            provider_id: candidate.provider_id,
            model_id: candidate.model_id,
            tokens_in: result.usage.inputTokens,
            tokens_out: result.usage.outputTokens,
            ok: true
          });

          return {
            ...result,
            provider_id: candidate.provider_id,
            model_id: candidate.model_id
          };
        } catch (err) {
          const kind = classifyDispatchError(err);
          this._recordCbFailure(candidate.provider_id, kind);

          this._emitEvent('freecompute_dispatch_error', {
            provider_id: candidate.provider_id,
            model_id: candidate.model_id,
            error: err.message
          });

          // Retry timeouts at most once per provider per request.
          if (kind === 'timeout' && attempt < maxTimeoutRetries) {
            attempt += 1;
            continue;
          }

          // Try next candidate
          break;
        }
      }
    }

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
      config: this.config
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
      if (entry.auth && entry.auth.type !== 'none' && entry.auth.type !== 'bearer_optional') {
        if (!hasAuthCredential(entry.auth, this._env)) {
          // Skip providers without configured credentials
          continue;
        }
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
    classifyDispatchError
  }
};
