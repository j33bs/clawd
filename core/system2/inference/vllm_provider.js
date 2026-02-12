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
async function probeVllmServer(options = {}) {
  const env = options.env || process.env;
  const baseUrl = options.baseUrl
    || env.OPENCLAW_VLLM_BASE_URL
    || 'http://127.0.0.1:18888/v1';

  const status = {
    ts: new Date().toISOString(),
    base_url: baseUrl,
    healthy: false,
    models: [],
    inference_ok: false,
    error: null
  };

  try {
    const provider = createVllmProvider({ env });
    // Override base URL if specified
    if (options.baseUrl) provider.baseUrl = options.baseUrl;

    const healthResult = await provider.health();
    status.healthy = healthResult.ok;
    status.models = healthResult.models || [];

    if (healthResult.ok && status.models.length > 0) {
      // Try a minimal inference
      try {
        const result = await provider.call({
          messages: [{ role: 'user', content: 'Respond with a single word: OK' }],
          metadata: { model: status.models[0], maxTokens: 8 }
        });
        status.inference_ok = Boolean(result.text);
      } catch (err) {
        status.inference_ok = false;
        status.error = `inference probe failed: ${err.message}`;
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
  const port = options.port || 18888;
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
