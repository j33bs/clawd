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

function main() {
  const env = process.env;
  const cfg = loadFreeComputeConfig(env);

  const lines = [];
  lines.push('=== System-2 Provider Diagnostics (safe) ===');
  lines.push(`freecompute_enabled=${cfg.enabled ? 'true' : 'false'}`);
  lines.push(`secrets_bridge_enabled=${cfg.secretsBridge && cfg.secretsBridge.enabled ? 'true' : 'false'}`);
  lines.push('');
  lines.push('providers:');

  const providers = [...CATALOG].sort((a, b) => a.provider_id.localeCompare(b.provider_id));
  for (const p of providers) {
    if (p.provider_id.startsWith('openai')) {
      lines.push(`- ${p.provider_id}: policy=disabled configured=n/a`);
      continue;
    }
    const auth = p.auth || {};
    const keys = [auth.env_var].concat(Array.isArray(auth.alias_env_vars) ? auth.alias_env_vars : []).filter(Boolean);
    const configured = isConfigured(p, env);
    lines.push(`- ${p.provider_id}: configured=${configured ? 'yes' : 'no'} auth_env_keys=${keys.length > 0 ? keys.join(',') : '(none)'}`);
  }

  process.stdout.write(lines.join('\n') + '\n');
}

main();
