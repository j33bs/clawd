'use strict';

/**
 * FreeComputeCloud — Module Barrel Export
 *
 * Entry point for the entire inference layer.
 * Feature-flagged: does nothing when ENABLE_FREECOMPUTE_CLOUD=0.
 */

const { REQUEST_CLASSES, ALL_REQUEST_CLASSES, PROVIDER_KINDS, AUTH_TYPES, TOOL_SUPPORT,
        QUOTA_MODES, BACKOFF_STRATEGIES, validateProviderEntry, validateCatalog } = require('./schemas');
const { loadFreeComputeConfig, REDACT_ENV_VARS, REDACT_HEADERS, redactIfSensitive } = require('./config');
const { CATALOG_VERSION, CATALOG, getProvider, queryProviders } = require('./catalog');
const { ProviderAdapter } = require('./provider_adapter');
const { SecretsBridge, PROVIDER_ENV_MAP, BACKEND_TYPES, maskSecretFingerprint } = require('./secrets_bridge');
const { QuotaLedger } = require('./quota_ledger');
const { routeRequest, explainRouting } = require('./router');
const { createVllmProvider, probeVllmServer, vllmStartCommand, buildVllmStatusArtifact } = require('./vllm_provider');
const { LocalVllmProvider, normalizeBaseUrl } = require('./local_vllm_provider');
const { ProviderRegistry, CB_STATES } = require('./provider_registry');

module.exports = {
  // Schemas
  REQUEST_CLASSES, ALL_REQUEST_CLASSES, PROVIDER_KINDS, AUTH_TYPES, TOOL_SUPPORT,
  QUOTA_MODES, BACKOFF_STRATEGIES, validateProviderEntry, validateCatalog,
  // Config
  loadFreeComputeConfig, REDACT_ENV_VARS, REDACT_HEADERS, redactIfSensitive,
  // Catalog
  CATALOG_VERSION, CATALOG, getProvider, queryProviders,
  // Adapter
  ProviderAdapter,
  // Secrets Bridge
  SecretsBridge, PROVIDER_ENV_MAP, BACKEND_TYPES, maskSecretFingerprint,
  // Quota
  QuotaLedger,
  // Router
  routeRequest, explainRouting,
  // vLLM
  createVllmProvider, probeVllmServer, vllmStartCommand, buildVllmStatusArtifact,
  LocalVllmProvider, normalizeBaseUrl,
  // Registry
  ProviderRegistry, CB_STATES
};
