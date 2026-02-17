'use strict';

/**
 * FreeComputeCloud — System 2 vLLM Config Resolver
 *
 * Resolves vLLM configuration with precedence:
 * 1. Explicit args (highest)
 * 2. System 2 env vars (SYSTEM2_VLLM_*)
 * 3. System 1 env vars (OPENCLAW_VLLM_*)
 * 4. Defaults (lowest)
 *
 * Safety: logs only key names and resolution path, never values.
 */

const LOG_KEYS = ['base_url', 'api_key', 'model'];
const { normalizeNodeId } = require('../../node_identity');

function hasAnySystem2Env(env) {
  return Boolean(
    env.SYSTEM2_VLLM_BASE_URL
    || env.SYSTEM2_VLLM_API_KEY
    || env.SYSTEM2_VLLM_MODEL
    || env.SYSTEM2_VLLM_TIMEOUT_MS
    || env.SYSTEM2_VLLM_MAX_RETRIES
    || env.SYSTEM2_VLLM_CB_OPEN_SECONDS
    || env.SYSTEM2_VLLM_MAX_CONCURRENCY
  );
}

function resolveSystem2VllmConfig(options = {}) {
  const env = options.env || process.env;
  const emit = options.emitEvent || (() => {});
  const normalizedNodeId = normalizeNodeId(
    options.nodeId || options.node_id || env.OPENCLAW_NODE_ID
  );
  const useSystem2Env = options.system2 === true || normalizedNodeId === 'c_lawd' || hasAnySystem2Env(env);

  // Precedence: explicit > c_lawd/system2 env > dali/system1 env > defaults
  const config = {
    base_url: options.baseUrl
      || (useSystem2Env ? env.SYSTEM2_VLLM_BASE_URL : null)
      || env.OPENCLAW_VLLM_BASE_URL
      || 'http://127.0.0.1:18888/v1',

    api_key: options.apiKey
      || (useSystem2Env ? env.SYSTEM2_VLLM_API_KEY : null)
      || env.OPENCLAW_VLLM_API_KEY
      || null,

    model: options.model
      || (useSystem2Env ? env.SYSTEM2_VLLM_MODEL : null)
      || env.OPENCLAW_VLLM_MODEL
      || null,

    timeout_ms: Number(
      options.timeoutMs
      || (useSystem2Env ? env.SYSTEM2_VLLM_TIMEOUT_MS : null)
      || env.OPENCLAW_VLLM_TIMEOUT_MS
      || 30000
    ),

    max_retries: Number(
      options.maxRetries
      || (useSystem2Env ? env.SYSTEM2_VLLM_MAX_RETRIES : null)
      || env.OPENCLAW_VLLM_MAX_RETRIES
      || 2
    ),

    cb_open_seconds: Number(
      options.cbOpenSeconds
      || (useSystem2Env ? env.SYSTEM2_VLLM_CB_OPEN_SECONDS : null)
      || env.OPENCLAW_VLLM_CB_OPEN_SECONDS
      || 60
    ),

    max_concurrent_requests: Number(
      options.maxConcurrentRequests
      || (useSystem2Env ? env.SYSTEM2_VLLM_MAX_CONCURRENCY : null)
      || env.OPENCLAW_VLLM_MAX_CONCURRENCY
      || 2
    )
  };

  // Log resolution (keys only, no values)
  const keys_resolved = {};
  for (const key of LOG_KEYS) {
    keys_resolved[key] = config[key] ? 'set' : 'missing';
  }
  emit('system2_vllm_config_resolved', {
    keys: keys_resolved,
    node_id: normalizedNodeId,
    base_url_source: (useSystem2Env && env.SYSTEM2_VLLM_BASE_URL) ? 'system2' : env.OPENCLAW_VLLM_BASE_URL ? 'system1' : 'default',
    api_key_source: (useSystem2Env && env.SYSTEM2_VLLM_API_KEY) ? 'system2' : env.OPENCLAW_VLLM_API_KEY ? 'system1' : 'missing'
  });

  // Fail-closed: required keys
  const missing = [];
  if (!config.base_url) missing.push('base_url');

  if (missing.length > 0) {
    const err = new Error(`System 2 vLLM config incomplete: missing [${missing.join(', ')}]`);
    err.code = 'SYSTEM2_CONFIG_INCOMPLETE';
    err.missing = missing;
    throw err;
  }

  return config;
}

module.exports = {
  resolveSystem2VllmConfig
};
