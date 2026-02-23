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
const { SecretsBridge } = require('../../core/system2/inference/secrets_bridge');
const { makeEnvelope, SCHEMA_ID } = require('./event_envelope');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const http = require('node:http');
const https = require('node:https');

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

function replayLogPath(env) {
  return env.OPENCLAW_REPLAY_LOG_PATH || path.join(os.homedir(), '.local', 'share', 'openclaw', 'replay', 'replay.jsonl');
}

function canaryEnvelopeLogPath(env) {
  return env.OPENCLAW_EVENT_ENVELOPE_LOG_PATH || path.join(os.homedir(), '.local', 'share', 'openclaw', 'events', 'gate_health.jsonl');
}

function coderLogPath(env) {
  return env.OPENCLAW_VLLM_CODER_LOG_PATH || path.join(os.homedir(), '.local', 'state', 'openclaw', 'vllm-coder.log');
}

function checkReplayWritable(env) {
  const target = replayLogPath(env);
  try {
    fs.mkdirSync(path.dirname(target), { recursive: true });
    const fd = fs.openSync(target, 'a');
    fs.closeSync(fd);
    return { writable: true, path: target, reason: 'ok' };
  } catch (err) {
    return { writable: false, path: target, reason: (err && (err.code || err.name)) || 'unknown' };
  }
}

function appendEnvelope(env, envelope) {
  const target = canaryEnvelopeLogPath(env);
  try {
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.appendFileSync(target, JSON.stringify(envelope) + '\n', 'utf8');
    return { ok: true, path: target };
  } catch (err) {
    return { ok: false, path: target, reason: (err && (err.code || err.name)) || 'unknown' };
  }
}

function parseCoderStartBlocked(line) {
  if (!line || !line.includes('VLLM_CODER_START_BLOCKED')) return null;
  const reasonMatch = String(line).match(/reason=([A-Z0-9_]+)/);
  const freeMatch = String(line).match(/free_mb=([A-Za-z0-9._-]+)/);
  const minMatch = String(line).match(/min_free_mb=([A-Za-z0-9._-]+)/);
  return {
    reason: (reasonMatch && reasonMatch[1]) ? reasonMatch[1] : 'BLOCKED',
    free_mb: (freeMatch && freeMatch[1]) ? freeMatch[1] : 'na',
    min_free_mb: (minMatch && minMatch[1]) ? minMatch[1] : 'na'
  };
}

function readCoderJournalTail(env) {
  if (env.PROVIDER_DIAG_JOURNAL_TEXT) {
    return { ok: true, text: String(env.PROVIDER_DIAG_JOURNAL_TEXT), source: 'env_override' };
  }
  if (env.PROVIDER_DIAG_JOURNAL_FORCE_UNAVAILABLE) {
    return { ok: false, unavailable: true, reason: String(env.PROVIDER_DIAG_JOURNAL_FORCE_UNAVAILABLE) };
  }
  try {
    const out = execFileSync(
      'journalctl',
      ['--user', '-u', 'openclaw-vllm-coder.service', '-n', '50', '--no-pager'],
      { encoding: 'utf8' }
    );
    return { ok: true, text: String(out || ''), source: 'journalctl' };
  } catch (err) {
    const code = err && (err.code || err.name);
    if (code === 'ENOENT' || code === 'EACCES') {
      return { ok: false, unavailable: true, reason: String(code || 'unavailable') };
    }
    return { ok: false, unavailable: false, reason: String(code || 'error') };
  }
}

function detectCoderDegradedReason(env) {
  const target = coderLogPath(env);
  try {
    if (fs.existsSync(target)) {
      const content = fs.readFileSync(target, 'utf8');
      const lines = content.trim().split(/\r?\n/).reverse();
      for (const line of lines.slice(0, 50)) {
        const parsed = parseCoderStartBlocked(line);
        if (parsed) {
          return {
            reason: parsed.reason,
            note: 'file_marker'
          };
        }
      }
    }
  } catch (_) {
    // Ignore file log errors. Journald fallback is the deterministic source of truth.
  }

  const journal = readCoderJournalTail(env);
  if (!journal.ok) {
    return {
      reason: 'UNAVAILABLE',
      note: 'journal_unavailable'
    };
  }
  const lines = String(journal.text || '').split(/\r?\n/).reverse();
  for (const line of lines) {
    const parsed = parseCoderStartBlocked(line);
    if (parsed) {
      return {
        reason: parsed.reason,
        note: 'journal_marker'
      };
    }
  }
  return { reason: 'NO_BLOCK_MARKER', note: 'journal_no_marker' };
}

function fetchText(urlString, timeoutMs) {
  return new Promise((resolve, reject) => {
    let parsed;
    try {
      parsed = new URL(urlString);
    } catch (err) {
      reject(new Error(`invalid_url:${err.message}`));
      return;
    }
    const client = parsed.protocol === 'https:' ? https : http;
    const req = client.request(
      parsed,
      { method: 'GET', timeout: timeoutMs },
      (res) => {
        let data = '';
        res.setEncoding('utf8');
        res.on('data', (chunk) => { data += chunk; });
        res.on('end', () => {
          resolve({ status: res.statusCode || 0, body: data });
        });
      }
    );
    req.on('timeout', () => req.destroy(new Error('timeout')));
    req.on('error', (err) => reject(err));
    req.end();
  });
}

async function probeCoderVllm(env) {
  const base = env.OPENCLAW_VLLM_CODER_BASE_URL || 'http://127.0.0.1:8002/v1';
  const modelsUrl = `${String(base).replace(/\/$/, '')}/models`;
  if (env.PROVIDER_DIAG_NO_PROBES === '1') {
    return {
      endpoint: modelsUrl,
      endpoint_present: false,
      models_fetch_ok: false,
      models_count: 0,
      reason: 'skipped'
    };
  }
  try {
    const res = await fetchText(modelsUrl, 5000);
    let modelsCount = 0;
    if (res.status >= 200 && res.status < 300) {
      try {
        const parsed = JSON.parse(res.body || '{}');
        if (parsed && Array.isArray(parsed.data)) modelsCount = parsed.data.length;
      } catch (_) {
        modelsCount = 0;
      }
      return {
        endpoint: modelsUrl,
        endpoint_present: true,
        models_fetch_ok: true,
        models_count: modelsCount,
        reason: 'ok'
      };
    }
    return {
      endpoint: modelsUrl,
      endpoint_present: false,
      models_fetch_ok: false,
      models_count: 0,
      reason: `http_${res.status}`
    };
  } catch (err) {
    return {
      endpoint: modelsUrl,
      endpoint_present: false,
      models_fetch_ok: false,
      models_count: 0,
      reason: (err && err.message) ? err.message.slice(0, 80) : 'unknown'
    };
  }
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
  const cloudEnabled = Boolean(cfg && cfg.enabled);
  const localEnabled = Boolean(cfg && cfg.vllmEnabled);
  const routingEnabledForProvider = pid === 'local_vllm' ? localEnabled : cloudEnabled;

  const eligible = Boolean(routingEnabledForProvider && enabled && configured);
  if (!routingEnabledForProvider && !reason) reason = 'disabled_by_policy';
  if (!eligible && !reason) reason = 'not_configured';

  return { configured, enabled, eligible, reason };
}

async function probeLocalVllm(env) {
  if (env.PROVIDER_DIAG_NO_PROBES === '1') {
    return {
      endpoint_present: false,
      models_fetch_ok: false,
      models_count: 0,
      generation_probe_ok: false,
      generation_probe_reason: 'skipped'
    };
  }
  const entry = getProvider('local_vllm');
  if (!entry) {
    return {
      endpoint_present: false,
      models_fetch_ok: false,
      models_count: 0,
      generation_probe_ok: false,
      generation_probe_reason: 'not_configured'
    };
  }
  try {
    const adapter = new ProviderAdapter(entry, { env });
    const health = await adapter.health();
    const models = (health && Array.isArray(health.models)) ? health.models : [];
    const gen = await adapter.generationProbe({ timeoutMs: 5000 });
    return {
      endpoint_present: Boolean(health && health.ok),
      models_fetch_ok: Boolean(health && health.ok),
      models_count: models.length,
      generation_probe_ok: Boolean(gen && gen.ok),
      generation_probe_reason: (gen && gen.ok) ? 'ok' : ((gen && gen.reason) || 'unknown')
    };
  } catch (_) {
    return {
      endpoint_present: false,
      models_fetch_ok: false,
      models_count: 0,
      generation_probe_ok: false,
      generation_probe_reason: 'unknown'
    };
  }
}

async function generateDiagnostics(envInput) {
  // Secret-safety: never mutate process.env during diagnostics.
  const env = { ...(envInput || process.env) };
  const cfg = loadFreeComputeConfig(env);

  const lines = [];
  lines.push('=== System-2 Provider Diagnostics (safe) ===');
  lines.push(`freecompute_enabled=${cfg.enabled ? 'true' : 'false'}`);
  const freecomputeKeys = ['ENABLE_FREECOMPUTE_CLOUD', 'ENABLE_FREECOMPUTE'];
  const seen = envKeysSeen(env, freecomputeKeys);
  lines.push(`freecompute_env_keys_seen=${seen.length ? seen.join(',') : '(none)'}`);
  lines.push(`secrets_bridge_enabled=${cfg.secretsBridge && cfg.secretsBridge.enabled ? 'true' : 'false'}`);

  // If the bridge is enabled, inject secrets into this process env so that
  // configured/eligible checks reflect real runtime behavior. Names only.
  if (cfg.secretsBridge && cfg.secretsBridge.enabled) {
    try {
      const bridge = new SecretsBridge({ env });
      const injection = bridge.injectRuntimeEnv(env);
      const injectedKeys = (injection && Array.isArray(injection.injected))
        ? injection.injected.map((r) => r.envVar).filter(Boolean)
        : [];
      lines.push(`secrets_bridge_injected_env_keys=${injectedKeys.length ? injectedKeys.join(',') : '(none)'}`);
    } catch (_) {
      lines.push('secrets_bridge_injected_env_keys=(error)');
    }
  }
  lines.push('');

  const localProbe = await probeLocalVllm(env);
  const coderProbe = await probeCoderVllm(env);
  const replay = checkReplayWritable(env);
  const coderDegraded = coderProbe.endpoint_present ? { reason: 'OK', note: 'endpoint_reachable' } : detectCoderDegradedReason(env);
  const coderDegradedReason = coderDegraded.reason || 'NO_BLOCK_MARKER';
  const coderStatus = coderProbe.endpoint_present ? 'UP' : (
    (coderDegradedReason === 'NO_BLOCK_MARKER' || coderDegradedReason === 'UNAVAILABLE') ? 'DOWN' : 'DEGRADED'
  );

  lines.push(`local_vllm_endpoint_present=${localProbe.endpoint_present ? 'true' : 'false'}`);
  lines.push(`local_vllm_models_fetch_ok=${localProbe.models_fetch_ok ? 'true' : 'false'}`);
  lines.push(`local_vllm_models_count=${localProbe.models_count}`);
  lines.push(`local_vllm_generation_probe_ok=${localProbe.generation_probe_ok ? 'true' : 'false'}`);
  lines.push(`local_vllm_generation_probe_reason=${localProbe.generation_probe_reason}`);
  lines.push(`coder_vllm_endpoint=${coderProbe.endpoint}`);
  lines.push(`coder_vllm_endpoint_present=${coderProbe.endpoint_present ? 'true' : 'false'}`);
  lines.push(`coder_vllm_models_fetch_ok=${coderProbe.models_fetch_ok ? 'true' : 'false'}`);
  lines.push(`coder_vllm_models_count=${coderProbe.models_count}`);
  lines.push(`coder_status=${coderStatus}`);
  lines.push(`coder_degraded_reason=${coderDegradedReason}`);
  lines.push(`coder_degraded_note=${coderDegraded.note || ''}`);
  lines.push(`replay_log_path=${replay.path}`);
  lines.push(`replay_log_writable=${replay.writable ? 'true' : 'false'}`);
  lines.push(`replay_log_reason=${replay.reason}`);
  lines.push(`event_envelope_schema=${SCHEMA_ID}`);
  lines.push('');

  const corrId = `provider_diag_${Date.now()}`;
  const envelope = makeEnvelope({
    event: 'provider_diag_status',
    severity: (coderStatus === 'UP' && replay.writable) ? 'INFO' : 'WARN',
    component: 'provider_diag',
    corr_id: corrId,
    details: {
      local_vllm_generation_probe_ok: localProbe.generation_probe_ok,
      coder_status: coderStatus,
      coder_degraded_reason: coderDegradedReason,
      replay_log_writable: replay.writable
    }
  });
  const envelopeWrite = appendEnvelope(env, envelope);
  lines.push(`event_envelope_log_path=${envelopeWrite.path}`);
  lines.push(`event_envelope_write_ok=${envelopeWrite.ok ? 'true' : 'false'}`);
  lines.push(`event_envelope_write_reason=${envelopeWrite.ok ? 'ok' : envelopeWrite.reason}`);
  lines.push('');
  lines.push('canary_recommendations:');
  lines.push('- run: python3 scripts/dali_canary_runner.py');
  lines.push('- optional timer: systemctl --user enable --now openclaw-canary.timer');
  lines.push('- if coder DEGRADED with VRAM_LOW, reduce load or raise VLLM_CODER_MIN_FREE_VRAM_MB policy');
  lines.push('');

  lines.push('providers:');

  const summaryRows = [];
  const providers = [...CATALOG].sort((a, b) => a.provider_id.localeCompare(b.provider_id));
  for (const p of providers) {
    const auth = p.auth || {};
    const keys = [auth.env_var].concat(Array.isArray(auth.alias_env_vars) ? auth.alias_env_vars : []).filter(Boolean);
    const s = classifyProvider(p, env, cfg);
    if (p.provider_id === 'local_vllm' && !localProbe.generation_probe_ok) {
      s.eligible = false;
      s.reason = 'generation_probe_failed';
    }
    const reason = s.eligible ? 'ok' : s.reason;
    lines.push(`- ${p.provider_id}: configured=${s.configured ? 'yes' : 'no'} enabled=${s.enabled ? 'yes' : 'no'} eligible=${s.eligible ? 'yes' : 'no'} reason=${reason} auth_env_keys=${keys.length > 0 ? keys.join(',') : '(none)'}`);
    summaryRows.push({ provider_id: p.provider_id, configured: s.configured, enabled: s.enabled, eligible: s.eligible, reason });
  }

  lines.push('');
  lines.push('providers_summary:');
  for (const row of summaryRows) {
    // Grep-friendly: provider_id at column 0. No auth_env_keys to reduce noise.
    lines.push(
      `${row.provider_id}: configured=${row.configured ? 'yes' : 'no'} enabled=${row.enabled ? 'yes' : 'no'} eligible=${row.eligible ? 'yes' : 'no'} reason=${row.reason}`
    );
  }

  return lines.join('\n') + '\n';
}

async function main() {
  const out = await generateDiagnostics(process.env);
  process.stdout.write(out);
}

if (require.main === module) {
  main().catch((err) => {
    process.stderr.write(`provider_diag_failed: ${err.message}\n`);
    process.exitCode = 1;
  });
}

module.exports = {
  generateDiagnostics
};
