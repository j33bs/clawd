#!/usr/bin/env node
'use strict';

/**
 * System-2 Provider Diagnostics (secret-safe)
 *
 * Prints only structural metadata:
 * - whether the Secrets Bridge is enabled
 * - which providers appear configured (env var present by name; no values)
 */

const { CATALOG } = require('../../core/system2/inference/catalog');
const { loadFreeComputeConfig } = require('../../core/system2/inference/config');
const { getProvider } = require('../../core/system2/inference/catalog');
const { ProviderAdapter } = require('../../core/system2/inference/provider_adapter');

function isConfigured(entry, env) {
  if (entry && entry.provider_id === 'remote_vllm') {
    const key = entry.base_url && entry.base_url.env_override;
    return !!(key && env[key]);
  }
  const auth = entry && entry.auth;
  if (!auth || auth.type === 'none' || auth.type === 'bearer_optional') return true;
  const keys = [auth.env_var].concat(Array.isArray(auth.alias_env_vars) ? auth.alias_env_vars : []);
  for (const k of keys) {
    if (k && env[k]) return true;
  }
  return false;
}

function envKeysSeen(env, keys) {
  return keys.filter((k) => k && env[k]);
}

function classifyProvider(entry, env, cfg) {
  const pid = entry.provider_id;

  // Compute "configured" (required knobs present).
  let configured = true;
  let reason = null;

  // Special-case: remote_vllm requires explicit base URL.
  if (pid === 'remote_vllm') {
    const key = entry.base_url && entry.base_url.env_override;
    configured = Boolean(key && env[key]);
    if (!configured) reason = 'not_configured';
  } else if (pid === 'openai') {
    // Make "missing_api_key" explicit when OPENAI_API_KEY is absent.
    const auth = entry.auth || {};
    const keys = [auth.env_var].concat(Array.isArray(auth.alias_env_vars) ? auth.alias_env_vars : []).filter(Boolean);
    configured = keys.some((k) => env[k]);
    if (!configured) reason = 'missing_api_key';
  } else {
    configured = isConfigured(entry, env);
    if (!configured) {
      const auth = entry.auth || {};
      reason = auth && auth.type && auth.type !== 'none' ? 'missing_api_key' : 'not_configured';
    }
  }

  // Compute "enabled" (policy/config allows consideration).
  let enabled = true;
  if (entry.policy_disabled) {
    enabled = false;
    reason = reason || 'disabled_by_policy';
  }
  if (pid === 'local_vllm' && !cfg.vllmEnabled) {
    enabled = false;
    reason = reason || 'disabled_by_policy';
  }
  if (cfg.providerDenylist && cfg.providerDenylist.includes(pid)) {
    enabled = false;
    reason = reason || 'disabled_by_policy';
  }
  if (entry.kind === 'external' && !entry.enabled_default) {
    if (cfg.providerAllowlist && cfg.providerAllowlist.length > 0 && !cfg.providerAllowlist.includes(pid)) {
      enabled = false;
      reason = reason || 'disabled_by_policy';
    }
  }

  // Compute "eligible" for automated routing (includes global feature flag).
  const eligible = Boolean(cfg.enabled && enabled && configured);
  if (!cfg.enabled && !reason) reason = 'disabled_by_policy';
  if (!eligible && !reason) reason = 'not_configured';

  return { configured, enabled, eligible, reason };
}

async function probeLocalVllm(env) {
  const entry = getProvider('local_vllm');
  if (!entry) {
    return { endpoint_present: false, models_fetch_ok: false, models_count: 0 };
  }
  try {
    const adapter = new ProviderAdapter(entry, { env });
    const health = await adapter.health();
    const models = (health && Array.isArray(health.models)) ? health.models : [];
    return {
      endpoint_present: Boolean(health && health.ok),
      models_fetch_ok: Boolean(health && health.ok),
      models_count: models.length
    };
  } catch (_) {
    return { endpoint_present: false, models_fetch_ok: false, models_count: 0 };
  }
}

async function main() {
  const env = process.env;
  const cfg = loadFreeComputeConfig(env);

  const lines = [];
  lines.push('=== System-2 Provider Diagnostics (safe) ===');
  lines.push(`freecompute_enabled=${cfg.enabled ? 'true' : 'false'}`);
  const freecomputeKeys = ['ENABLE_FREECOMPUTE_CLOUD', 'ENABLE_FREECOMPUTE'];
  const seen = envKeysSeen(env, freecomputeKeys);
  lines.push(`freecompute_env_keys_seen=${seen.length ? seen.join(',') : '(none)'}`);
  lines.push(`secrets_bridge_enabled=${cfg.secretsBridge && cfg.secretsBridge.enabled ? 'true' : 'false'}`);
  lines.push('');

  const localProbe = await probeLocalVllm(env);
  lines.push(`local_vllm_endpoint_present=${localProbe.endpoint_present ? 'true' : 'false'}`);
  lines.push(`local_vllm_models_fetch_ok=${localProbe.models_fetch_ok ? 'true' : 'false'}`);
  lines.push(`local_vllm_models_count=${localProbe.models_count}`);
  lines.push('');
  lines.push('providers:');

  const providers = [...CATALOG].sort((a, b) => a.provider_id.localeCompare(b.provider_id));
  for (const p of providers) {
    const auth = p.auth || {};
    const keys = [auth.env_var].concat(Array.isArray(auth.alias_env_vars) ? auth.alias_env_vars : []).filter(Boolean);
    const s = classifyProvider(p, env, cfg);
    lines.push(
      `- ${p.provider_id}: configured=${s.configured ? 'yes' : 'no'} enabled=${s.enabled ? 'yes' : 'no'} eligible=${s.eligible ? 'yes' : 'no'} reason=${s.eligible ? 'ok' : s.reason} auth_env_keys=${keys.length > 0 ? keys.join(',') : '(none)'}`
    );
  }

  process.stdout.write(lines.join('\n') + '\n');
}

main().catch((err) => {
  process.stderr.write(`provider_diag_failed: ${err.message}\n`);
  process.exitCode = 1;
});
