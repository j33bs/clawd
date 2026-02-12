'use strict';

/**
 * FreeComputeCloud — Normalized Capability Schemas
 *
 * Data-driven schema definitions for provider catalog entries,
 * request classes, constraints, and cost models.
 *
 * LOAR-aligned: schemas are stable contracts; only catalog DATA changes
 * when adding providers. No code changes needed to onboard a new provider.
 */

// ── Request Classes ──────────────────────────────────────────────────

const REQUEST_CLASSES = Object.freeze({
  FAST_CHAT: 'fast_chat',
  LONG_CONTEXT: 'long_context',
  CODE: 'code',
  BATCH: 'batch',
  TOOL_USE: 'tool_use',
  EMBEDDINGS: 'embeddings'
});

const ALL_REQUEST_CLASSES = Object.freeze(Object.values(REQUEST_CLASSES));

// ── Constraint Types ─────────────────────────────────────────────────

const QUOTA_MODES = Object.freeze({
  LOCAL_BUDGETED: 'local_budgeted',
  FREE_QUOTA_PREFERRED: 'free_quota_preferred',
  STANDARD: 'standard'
});

const BACKOFF_STRATEGIES = Object.freeze({
  BOUNDED_EXPONENTIAL: 'bounded_exponential',
  LINEAR: 'linear',
  NONE: 'none'
});

const PROVIDER_KINDS = Object.freeze({
  LOCAL: 'local',
  EXTERNAL: 'external'
});

const AUTH_TYPES = Object.freeze({
  BEARER: 'bearer',
  BEARER_OPTIONAL: 'bearer_optional',
  API_KEY: 'api_key',
  NONE: 'none'
});

const TOOL_SUPPORT = Object.freeze({
  NONE: 'none',
  NATIVE: 'native',
  VIA_ADAPTER: 'via_adapter'
});

// ── Provider Catalog Schema Validation ───────────────────────────────

const REQUIRED_PROVIDER_FIELDS = [
  'provider_id', 'kind', 'protocol', 'base_url', 'auth',
  'enabled_default', 'models', 'constraints', 'healthcheck',
  'routing_tags', 'evidence'
];

const REQUIRED_MODEL_FIELDS = [
  'model_id', 'task_classes', 'context_window_hint', 'tool_support', 'notes'
];

/**
 * Validate a single provider catalog entry.
 * @param {object} entry
 * @returns {{ ok: boolean, errors: string[] }}
 */
function validateProviderEntry(entry) {
  const errors = [];
  if (!entry || typeof entry !== 'object') {
    return { ok: false, errors: ['entry must be an object'] };
  }

  for (const field of REQUIRED_PROVIDER_FIELDS) {
    if (entry[field] === undefined || entry[field] === null) {
      errors.push(`missing required field: ${field}`);
    }
  }

  if (entry.kind && !Object.values(PROVIDER_KINDS).includes(entry.kind)) {
    errors.push(`invalid kind: ${entry.kind}`);
  }

  if (entry.auth && entry.auth.type && !Object.values(AUTH_TYPES).includes(entry.auth.type)) {
    errors.push(`invalid auth.type: ${entry.auth.type}`);
  }

  if (Array.isArray(entry.models)) {
    for (let i = 0; i < entry.models.length; i++) {
      const model = entry.models[i];
      for (const field of REQUIRED_MODEL_FIELDS) {
        if (model[field] === undefined) {
          errors.push(`models[${i}]: missing required field: ${field}`);
        }
      }
      if (Array.isArray(model.task_classes)) {
        for (const tc of model.task_classes) {
          if (!ALL_REQUEST_CLASSES.includes(tc)) {
            errors.push(`models[${i}]: invalid task_class: ${tc}`);
          }
        }
      }
      if (model.tool_support && !Object.values(TOOL_SUPPORT).includes(model.tool_support)) {
        errors.push(`models[${i}]: invalid tool_support: ${model.tool_support}`);
      }
    }
  }

  if (entry.routing_tags && typeof entry.routing_tags === 'object') {
    if (entry.routing_tags.prefers && !Array.isArray(entry.routing_tags.prefers)) {
      errors.push('routing_tags.prefers must be an array');
    }
    if (entry.routing_tags.avoids && !Array.isArray(entry.routing_tags.avoids)) {
      errors.push('routing_tags.avoids must be an array');
    }
  }

  return { ok: errors.length === 0, errors };
}

/**
 * Validate the full catalog array.
 * @param {object[]} catalog
 * @returns {{ ok: boolean, errors: string[], validCount: number }}
 */
function validateCatalog(catalog) {
  if (!Array.isArray(catalog)) {
    return { ok: false, errors: ['catalog must be an array'], validCount: 0 };
  }
  const allErrors = [];
  let valid = 0;
  for (let i = 0; i < catalog.length; i++) {
    const result = validateProviderEntry(catalog[i]);
    if (result.ok) {
      valid++;
    } else {
      for (const err of result.errors) {
        allErrors.push(`catalog[${i}] (${catalog[i].provider_id || '?'}): ${err}`);
      }
    }
  }
  return { ok: allErrors.length === 0, errors: allErrors, validCount: valid };
}

module.exports = {
  REQUEST_CLASSES,
  ALL_REQUEST_CLASSES,
  QUOTA_MODES,
  BACKOFF_STRATEGIES,
  PROVIDER_KINDS,
  AUTH_TYPES,
  TOOL_SUPPORT,
  REQUIRED_PROVIDER_FIELDS,
  REQUIRED_MODEL_FIELDS,
  validateProviderEntry,
  validateCatalog
};
