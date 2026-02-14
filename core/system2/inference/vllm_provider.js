'use strict';

/**
 * FreeComputeCloud — Local vLLM Provider
 *
 * Wraps a vLLM OpenAI-compatible server running locally (or on LAN).
 * Primary use: System-1 local inference offload.
 *
 * Features:
 *   - /v1/models probe for model discovery
 *   - Healthcheck with connection + inference validation
 *   - Concurrency limiter (bounded parallelism)
 *   - Status artifact writer (pid/port/model/timestamp)
 */

const { ProviderAdapter } = require('./provider_adapter');
const { getProvider } = require('./catalog');
const { resolveSystem2VllmConfig } = require('./system2_config_resolver');

/**
 * Create a vLLM provider adapter with discovery.
 *
 * @param {object} [options]
 * @param {object} [options.env]       - Environment variable source
 * @param {function} [options.emitEvent] - Event emitter
 * @returns {ProviderAdapter}
 */
function createVllmProvider(options = {}) {
  const entry = getProvider('local_vllm');
  if (!entry) {
    throw new Error('local_vllm not found in catalog');
  }

  if (options.system2 === true) {
    const env = options.env || process.env;
    const cfg = resolveSystem2VllmConfig({
      env,
      emitEvent: options.emitEvent,
      baseUrl: options.baseUrl,
      apiKey: options.apiKey,
      model: options.model,
      timeoutMs: options.timeoutMs,
      maxRetries: options.maxRetries,
      cbOpenSeconds: options.cbOpenSeconds,
      maxConcurrentRequests: options.maxConcurrentRequests
    });

    const resolvedEnv = { ...env };
    if (cfg.base_url) resolvedEnv.OPENCLAW_VLLM_BASE_URL = cfg.base_url;
    if (cfg.api_key) resolvedEnv.OPENCLAW_VLLM_API_KEY = cfg.api_key;
    if (cfg.model) resolvedEnv.OPENCLAW_VLLM_MODEL = cfg.model;

    return new ProviderAdapter(entry, { ...options, env: resolvedEnv });
  }

  return new ProviderAdapter(entry, options);
}

/**
 * Probe a vLLM server and return status artifact.
 *
 * @param {object} [options]
 * @param {string} [options.baseUrl]
 * @param {object} [options.env]
 * @returns {Promise<object>} Status artifact
 */
async function probeVllmServer(entry, options = {}, { providerFactory } = {}) {
  if (!entry || !entry.provider_id) {
    // Back-compat: allow probeVllmServer(options) call style.
    options = entry || options || {};
    entry = getProvider('local_vllm');
  }
  if (!entry) {
    throw new Error('local_vllm not found in catalog');
  }

  const env = options.env || process.env;
  const baseUrl = options.baseUrl
    || env.OPENCLAW_VLLM_BASE_URL
    || 'http://127.0.0.1:8000/v1';
  const system2Cfg = options.system2 === true
    ? resolveSystem2VllmConfig({
        env,
        emitEvent: options.emitEvent,
        baseUrl: options.baseUrl,
        apiKey: options.apiKey,
        model: options.model,
        timeoutMs: options.timeoutMs,
        maxRetries: options.maxRetries,
        cbOpenSeconds: options.cbOpenSeconds,
        maxConcurrentRequests: options.maxConcurrentRequests
      })
    : null;

  const status = {
    ts: new Date().toISOString(),
    base_url: system2Cfg ? system2Cfg.base_url : baseUrl,
    healthy: false,
    models: [],
    inference_ok: false,
    generation_probe_ok: false,
    generation_probe_reason: null,
    error: null
  };

  try {
    const derivedEnv = system2Cfg
      ? {
          ...env,
          OPENCLAW_VLLM_BASE_URL: system2Cfg.base_url || env.OPENCLAW_VLLM_BASE_URL,
          OPENCLAW_VLLM_API_KEY: system2Cfg.api_key || env.OPENCLAW_VLLM_API_KEY,
          OPENCLAW_VLLM_MODEL: system2Cfg.model || env.OPENCLAW_VLLM_MODEL
        }
      : env;

    const derivedOptions = {
      env: derivedEnv,
      emitEvent: options.emitEvent,
      system2: options.system2 === true,
      baseUrl: options.baseUrl,
      apiKey: options.apiKey,
      model: options.model,
      timeoutMs: options.timeoutMs,
      maxRetries: options.maxRetries,
      cbOpenSeconds: options.cbOpenSeconds,
      maxConcurrentRequests: options.maxConcurrentRequests
    };

    const makeProvider = providerFactory ?? ((e, o) => new ProviderAdapter(e, o));
    const provider = makeProvider(entry, derivedOptions);
    // Override base URL if specified
    if (options.baseUrl) provider.baseUrl = options.baseUrl;

    const healthResult = await provider.health();
    status.healthy = healthResult.ok;
    status.models = healthResult.models || [];

    if (healthResult.ok && status.models.length > 0) {
      // Deterministic generation probe (short timeout) to catch "HTTP alive but generation wedged".
      try {
        const probeModel = (system2Cfg && system2Cfg.model) || status.models[0];
        if (typeof provider.generationProbe === 'function') {
          const timeoutMs = Number(env.FREECOMPUTE_LOCAL_VLLM_PROBE_TIMEOUT_MS || 5000);
          const gen = await provider.generationProbe({ timeoutMs, model: probeModel });
          status.generation_probe_ok = Boolean(gen && gen.ok);
          status.generation_probe_reason = (gen && gen.ok) ? 'ok' : ((gen && gen.reason) || 'unknown');
          status.inference_ok = status.generation_probe_ok;
          if (!status.generation_probe_ok && !status.error) {
            status.error = `generation probe failed: ${status.generation_probe_reason}`;
          }
        } else {
          status.generation_probe_ok = false;
          status.generation_probe_reason = 'not_supported';
          status.inference_ok = false;
          if (!status.error) status.error = 'generation probe not supported by provider';
        }
      } catch (err) {
        status.generation_probe_ok = false;
        status.generation_probe_reason = 'unknown';
        status.inference_ok = false;
        status.error = `generation probe failed: ${err.message}`;
      }
    }
  } catch (err) {
    status.error = err.message;
  }

  return status;
}

/**
 * Generate a dry-run start command for vLLM server.
 * Prints the command without executing it or exposing secrets.
 *
 * @param {object} [options]
 * @param {string} [options.model]    - Model to serve
 * @param {number} [options.port]     - Port number
 * @param {string} [options.gpuMemoryUtilization] - e.g. '0.90'
 * @returns {string} The command string
 */
function vllmStartCommand(options = {}) {
  const model = options.model || '<MODEL_NAME>';
  const port = options.port || 8000;
  const gpuUtil = options.gpuMemoryUtilization || '0.90';

  const parts = [
    'python -m vllm.entrypoints.openai.api_server',
    `--model ${model}`,
    `--port ${port}`,
    `--gpu-memory-utilization ${gpuUtil}`,
    '--trust-remote-code'
  ];

  if (options.apiKey) {
    parts.push('--api-key $OPENCLAW_VLLM_API_KEY');
  }

  return parts.join(' \\\n  ');
}

/**
 * Generate a vLLM status artifact JSON for writing to disk.
 * @param {object} probeResult - Output of probeVllmServer()
 * @returns {object}
 */
function buildVllmStatusArtifact(probeResult) {
  return {
    version: '0.1',
    type: 'vllm_status',
    ...probeResult
  };
}

module.exports = {
  createVllmProvider,
  probeVllmServer,
  vllmStartCommand,
  buildVllmStatusArtifact
};
