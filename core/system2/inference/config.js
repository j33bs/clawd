'use strict';

/**
 * FreeComputeCloud — Governance Configuration
 *
 * Single source of truth for feature flags, global caps, and per-task-class
 * limits. All values sourced from environment variables with conservative
 * defaults. LOAR-aligned: changing compute policy = changing config, not code.
 */

const { REQUEST_CLASSES } = require('./schemas');

// ── Feature Flags ────────────────────────────────────────────────────

/**
 * Load governance config from environment (or supplied env object).
 * @param {object} [env] - Environment variables (defaults to process.env)
 * @returns {object}
 */
function loadFreeComputeConfig(env) {
  const e = env || process.env;

  const enabled = e.ENABLE_FREECOMPUTE_CLOUD === '1';
  const vllmEnabled = e.ENABLE_LOCAL_VLLM === '1';

  // ── Per-provider enable/disable ──
  const providerAllowlist = (e.FREECOMPUTE_PROVIDER_ALLOWLIST || '')
    .split(',').map((s) => s.trim()).filter(Boolean);
  const providerDenylist = (e.FREECOMPUTE_PROVIDER_DENYLIST || '')
    .split(',').map((s) => s.trim()).filter(Boolean);

  // ── Global caps ──
  const globalMaxDailyRequests = Number(e.FREECOMPUTE_MAX_DAILY_REQUESTS || 200);
  const globalMaxRpm = Number(e.FREECOMPUTE_MAX_RPM || 30);
  const globalMaxDailyTokens = Number(e.FREECOMPUTE_MAX_DAILY_TOKENS || 2000000);

  // ── Circuit breaker thresholds ──
  const cbConsecutiveFailures = Number(e.FREECOMPUTE_CB_FAILURES || 3);
  const cbOpenSeconds = Number(e.FREECOMPUTE_CB_OPEN_SECONDS || 120);
  const cbHalfOpenProbeSeconds = Number(e.FREECOMPUTE_CB_PROBE_SECONDS || 60);
  const cbTimeoutMs = Number(e.FREECOMPUTE_CB_TIMEOUT_MS || 30000);

  // ── Per-task-class caps (conservative defaults) ──
  const taskClassCaps = {};
  for (const tc of Object.values(REQUEST_CLASSES)) {
    const prefix = `FREECOMPUTE_${tc.toUpperCase()}`;
    taskClassCaps[tc] = {
      maxExternalFreeRpm: Number(e[`${prefix}_MAX_RPM`] || _defaultRpmForClass(tc)),
      maxRetries: Number(e[`${prefix}_MAX_RETRIES`] || _defaultRetriesForClass(tc))
    };
  }

  // ── Ledger config ──
  const ledgerPath = e.FREECOMPUTE_LEDGER_PATH || '.tmp/quota-ledger';
  const ledgerResetHour = Number(e.FREECOMPUTE_LEDGER_RESET_HOUR || 0); // 0 = midnight UTC

  return {
    enabled,
    vllmEnabled,
    providerAllowlist,
    providerDenylist,
    globalMaxDailyRequests,
    globalMaxRpm,
    globalMaxDailyTokens,
    circuitBreaker: {
      consecutiveFailures: cbConsecutiveFailures,
      openSeconds: cbOpenSeconds,
      halfOpenProbeSeconds: cbHalfOpenProbeSeconds,
      timeoutMs: cbTimeoutMs
    },
    taskClassCaps,
    ledger: {
      path: ledgerPath,
      resetHour: ledgerResetHour
    },
    secretsBridge: {
      enabled: e.ENABLE_SECRETS_BRIDGE === '1',
      backend: String(e.SECRETS_BACKEND || 'auto').toLowerCase(),
      allowUiIntake: e.SECRETS_ALLOW_UI_INTAKE === '1',
      uiLocalhostOnly: e.SECRETS_UI_LOCALHOST_ONLY !== '0'
    }
  };
}

function _defaultRpmForClass(tc) {
  switch (tc) {
    case REQUEST_CLASSES.FAST_CHAT: return 20;
    case REQUEST_CLASSES.LONG_CONTEXT: return 5;
    case REQUEST_CLASSES.CODE: return 10;
    case REQUEST_CLASSES.BATCH: return 5;
    case REQUEST_CLASSES.TOOL_USE: return 10;
    case REQUEST_CLASSES.EMBEDDINGS: return 10;
    default: return 5;
  }
}

function _defaultRetriesForClass(tc) {
  switch (tc) {
    case REQUEST_CLASSES.LONG_CONTEXT: return 1;
    case REQUEST_CLASSES.BATCH: return 1;
    default: return 2;
  }
}

// ── Redaction Rules ──────────────────────────────────────────────────

const REDACT_ENV_VARS = Object.freeze([
  'OPENCLAW_VLLM_API_KEY',
  'OPENCLAW_GEMINI_API_KEY',
  'OPENCLAW_GROQ_API_KEY',
  'OPENCLAW_QWEN_API_KEY',
  'OPENCLAW_OPENROUTER_API_KEY'
]);

const REDACT_HEADERS = Object.freeze([
  'authorization',
  'x-api-key'
]);

/**
 * Redact a value if its key matches a sensitive pattern.
 * @param {string} key
 * @param {*} value
 * @returns {*}
 */
function redactIfSensitive(key, value) {
  if (typeof key !== 'string') return value;
  const lower = key.toLowerCase();
  if (REDACT_HEADERS.includes(lower)) return '[REDACTED]';
  if (REDACT_ENV_VARS.some((v) => lower.includes(v.toLowerCase()))) return '[REDACTED]';
  if (/api[_-]?key|token|secret|credential|authorization|password/i.test(lower)) return '[REDACTED]';
  if (typeof value === 'string' && /^(sk-|gsk_|Bearer\s)/i.test(value)) return '[REDACTED]';
  return value;
}

module.exports = {
  loadFreeComputeConfig,
  REDACT_ENV_VARS,
  REDACT_HEADERS,
  redactIfSensitive
};
