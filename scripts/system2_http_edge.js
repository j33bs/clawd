#!/usr/bin/env node
'use strict';

/**
 * Secure HTTP edge for System-2 gateway.
 *
 * Requirements:
 * - Mandatory Bearer auth (multi-token identity map)
 * - Rate limiting per identity
 * - Request size limits
 * - Safe audit logs (no Authorization header values, no bodies)
 * - Optional websocket/tcp upgrade proxy (ask-first required by default)
 *
 * No outbound internet. Proxies to local upstream only by default.
 */

const http = require('node:http');
const net = require('node:net');
const { randomUUID, createHash, createHmac, timingSafeEqual } = require('node:crypto');
const fs = require('node:fs');

const { classifyRequest } = require('../core/system2/security/trust_boundary');
const { requireApproval } = require('../core/system2/security/ask_first');
const { createAuditSink } = require('../core/system2/security/audit_sink');

function nowUtcIso() {
  return new Date().toISOString();
}

function parseTokenMap(raw) {
  // Format: "label:token,label2:token2"
  const out = new Map();
  const s = String(raw || '').trim();
  if (!s) return out;
  for (const part of s.split(',')) {
    const tok = part.trim();
    if (!tok) continue;
    const idx = tok.indexOf(':');
    if (idx <= 0 || idx + 1 >= tok.length) continue;
    const label = tok.slice(0, idx).trim();
    const token = tok.slice(idx + 1).trim();
    if (!label || !token) continue;
    out.set(token, label);
  }
  return out;
}

function parseKeyMap(raw) {
  // Format: "id:secret,id2:secret2"
  const out = new Map();
  const s = String(raw || '').trim();
  if (!s) return out;
  for (const part of s.split(',')) {
    const tok = part.trim();
    if (!tok) continue;
    const idx = tok.indexOf(':');
    if (idx <= 0 || idx + 1 >= tok.length) continue;
    const id = tok.slice(0, idx).trim();
    const secret = tok.slice(idx + 1).trim();
    if (!id || !secret) continue;
    out.set(id, secret);
  }
  return out;
}

function requireSecretsFile0600(filePath, { strictPerms } = {}) {
  const p = String(filePath || '').trim();
  if (!p) return;

  let st;
  try {
    st = fs.lstatSync(p);
  } catch (_) {
    const err = new Error(`secrets file not found: ${p}`);
    err.code = 'EDGE_SECRETS_FILE_MISSING';
    throw err;
  }

  if (!st.isFile()) {
    const err = new Error(`secrets file must be a regular file: ${p}`);
    err.code = 'EDGE_SECRETS_FILE_NOT_REGULAR';
    throw err;
  }

  if (typeof st.isSymbolicLink === 'function' && st.isSymbolicLink()) {
    const err = new Error(`secrets file must not be a symlink: ${p}`);
    err.code = 'EDGE_SECRETS_FILE_SYMLINK';
    throw err;
  }

  if (strictPerms) {
    const mode = st.mode & 0o777;
    if (mode !== 0o600) {
      const err = new Error(`secrets file must have permissions 0600: ${p}`);
      err.code = 'EDGE_SECRETS_FILE_BAD_MODE';
      throw err;
    }
  }
}

function readSecretsFile(filePath, { strictPerms } = {}) {
  const p = String(filePath || '').trim();
  requireSecretsFile0600(p, { strictPerms });
  return String(fs.readFileSync(p, 'utf8') || '').trim();
}

function extractBearer(req) {
  const hdr = req.headers && req.headers.authorization;
  if (!hdr) return null;
  const s = Array.isArray(hdr) ? hdr[0] : String(hdr);
  const m = s.match(/^\s*Bearer\s+(.+?)\s*$/i);
  return m ? m[1] : null;
}

function safeHeaderString(value) {
  // Never log auth headers; keep this conservative.
  if (value == null) return '';
  return String(value);
}

function isLoopbackBind(host) {
  if (host === '::1') return true;
  if (host === '127.0.0.1') return true;
  if (host.startsWith('127.')) return true; // 127/8
  return false;
}

function isLoopbackRemote(remoteAddress) {
  const a = String(remoteAddress || '');
  if (!a) return false;
  if (a === '127.0.0.1' || a === '::1') return true;
  if (a.startsWith('::ffff:127.')) return true;
  return false;
}

function sha256Hex(buf) {
  const b = buf && Buffer.isBuffer(buf) ? buf : Buffer.from(buf || '');
  return createHash('sha256').update(b).digest('hex');
}

function hmacHex(secret, msg) {
  return createHmac('sha256', String(secret)).update(String(msg)).digest('hex');
}

function safeTimingEqualHex(expectedHex, providedHex) {
  try {
    const a = Buffer.from(String(expectedHex || ''), 'hex');
    const b = Buffer.from(String(providedHex || ''), 'hex');
    if (a.length !== b.length || a.length === 0) return false;
    return timingSafeEqual(a, b);
  } catch (_) {
    return false;
  }
}

function approvalStatusFromError(error) {
  const code = error && error.code;
  return (code === 'APPROVAL_REQUIRED' || code === 'TOOL_DENIED') ? 403 : 500;
}

function isJsonContentType(req) {
  const raw = req && req.headers ? req.headers['content-type'] : '';
  const v = Array.isArray(raw) ? raw[0] : raw;
  return String(v || '').toLowerCase().includes('application/json');
}

function normalizeToolArgs(args) {
  if (args == null) return null;
  if (typeof args === 'string') {
    const trimmed = args.trim();
    if (!trimmed) return null;
    try {
      const parsed = JSON.parse(trimmed);
      return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : null;
    } catch (_) {
      return null;
    }
  }
  return (typeof args === 'object' && !Array.isArray(args)) ? args : null;
}

function detectMalformedReadToolCall(payload) {
  if (!payload || typeof payload !== 'object') return null;

  const queue = [payload];
  const seen = new Set();
  let inspected = 0;
  while (queue.length > 0 && inspected < 200) {
    const node = queue.shift();
    if (!node || typeof node !== 'object') continue;
    if (seen.has(node)) continue;
    seen.add(node);
    inspected += 1;

    if (!Array.isArray(node)) {
      const rawName = node.tool || node.name || node.method
        || (node.function && node.function.name)
        || node.function_name;
      const toolName = String(rawName || '').trim().toLowerCase();
      if (toolName === 'read') {
        const args = normalizeToolArgs(
          node.args ?? node.arguments ?? node.input ?? node.params
          ?? (node.function && node.function.arguments)
        );
        if (!args || typeof args.path !== 'string' || !args.path.trim()) {
          return { reason: 'read_requires_non_empty_path' };
        }
      }
    }

    const values = Array.isArray(node) ? node : Object.values(node);
    for (const value of values) {
      if (value && typeof value === 'object') queue.push(value);
    }
  }
  return null;
}

function parseListLike(raw) {
  if (Array.isArray(raw)) {
    return raw.map((v) => String(v || '').trim()).filter(Boolean);
  }
  const s = String(raw || '').trim();
  if (!s) return [];
  if (s.startsWith('[')) {
    try {
      const parsed = JSON.parse(s);
      if (Array.isArray(parsed)) {
        return parsed.map((v) => String(v || '').trim()).filter(Boolean);
      }
    } catch (_) {}
  }
  return s.split(',').map((v) => v.trim()).filter(Boolean);
}

function isMachineRoutePath(pathname) {
  const p = String(pathname || '/');
  return (
    p === '/health'
    || p === '/status'
    || p === '/ready'
    || p.startsWith('/diag')
    || p.startsWith('/api')
  );
}

function hasHtmlContentType(value) {
  const raw = Array.isArray(value) ? value.join(',') : value;
  return String(raw || '').toLowerCase().includes('text/html');
}

function shouldServeSpaFallback(input = {}) {
  const method = String(input.method || 'GET').toUpperCase();
  const pathname = String(input.pathname || '/');
  const accept = String(input.accept || '').toLowerCase();
  if (method !== 'GET') return false;
  if (!accept.includes('text/html')) return false;
  if (isMachineRoutePath(pathname)) return false;
  if (pathname.startsWith('/rpc/')) return false;
  return true;
}

function computeRuntimeDiag(input = {}) {
  const nowMs = Number.isFinite(input.nowMs) ? Number(input.nowMs) : Date.now();
  const eventLoopLagMs = Math.max(0, Number(input.eventLoopLagMs || 0));
  const eventLoopLagMaxMs = Math.max(0, Number(input.eventLoopLagMaxMs || 0));
  const eventLoopSamples = Math.max(0, Number(input.eventLoopSamples || 0));
  const eventLoopLastSampleTs = Number.isFinite(input.eventLoopLastSampleTs)
    ? Number(input.eventLoopLastSampleTs)
    : nowMs;
  const eventLoopStallMs = Math.max(250, Number(input.eventLoopStallMs || 5000));
  const lastSampleAgeMs = Math.max(0, nowMs - eventLoopLastSampleTs);
  const eventLoopStalled = eventLoopLagMs > eventLoopStallMs || lastSampleAgeMs > eventLoopStallMs * 2;

  return {
    event_loop_lag_ms: eventLoopLagMs,
    event_loop_lag_max_ms: eventLoopLagMaxMs,
    event_loop_samples: eventLoopSamples,
    event_loop_last_sample_ts: new Date(eventLoopLastSampleTs).toISOString(),
    event_loop_last_sample_age_ms: lastSampleAgeMs,
    event_loop_stall_after_ms: eventLoopStallMs,
    event_loop_stalled: eventLoopStalled,
    inflight_global: Math.max(0, Number(input.inflightGlobal || 0)),
    inflight_identities: Math.max(0, Number(input.inflightIdentities || 0)),
  };
}

function computeTelegramLaneDiag(input = {}) {
  const dmPolicy = String(input.dmPolicy || '').trim().toLowerCase();
  const groupPolicy = String(input.groupPolicy || '').trim().toLowerCase();
  const allowlist = parseListLike(input.allowlist);
  const pairings = parseListLike(input.pairings);
  const telegramEnabled = Boolean(input.telegramEnabled);
  const staleAfterMs = Math.max(1000, Number(input.staleAfterMs || 300000));
  const nowMs = Number.isFinite(input.nowMs) ? Number(input.nowMs) : Date.now();
  const lastIngestTs = Number.isFinite(input.lastIngestTs) ? Number(input.lastIngestTs) : null;
  const lastSendTs = Number.isFinite(input.lastSendTs) ? Number(input.lastSendTs) : null;
  const ingestAgeMs = lastIngestTs == null ? null : Math.max(0, nowMs - lastIngestTs);
  const sendAgeMs = lastSendTs == null ? null : Math.max(0, nowMs - lastSendTs);
  const ingestStale = telegramEnabled && ingestAgeMs != null && ingestAgeMs > staleAfterMs;
  const connected = input.connected == null ? null : Boolean(input.connected);
  const backoffState = input.backoffState == null ? null : String(input.backoffState);

  const restrictedDm = dmPolicy === 'pairing' || dmPolicy === 'allowlist';
  const restrictedGroup = groupPolicy === 'pairing' || groupPolicy === 'allowlist';
  const policyRestricted = restrictedDm || restrictedGroup;
  const emptyAdmissions = allowlist.length === 0 && pairings.length === 0;
  const lockedOut = policyRestricted && emptyAdmissions;

  const reasons = [];
  if (lockedOut) {
    reasons.push('policy_restricts_telegram_and_no_allowlist_or_pairings');
  }
  if (ingestStale) {
    reasons.push('telegram_ingest_stale');
  }

  return {
    enabled: telegramEnabled,
    dm_policy: dmPolicy || null,
    group_policy: groupPolicy || null,
    allowlist_count: allowlist.length,
    pairings_count: pairings.length,
    policy_restricted: policyRestricted,
    telegram_lane_locked_out: lockedOut,
    last_telegram_ingest_ts: lastIngestTs == null ? null : new Date(lastIngestTs).toISOString(),
    last_telegram_send_ts: lastSendTs == null ? null : new Date(lastSendTs).toISOString(),
    telegram_ingest_age_ms: ingestAgeMs,
    telegram_send_age_ms: sendAgeMs,
    telegram_stale_after_ms: staleAfterMs,
    telegram_ingest_stale: ingestStale,
    connected,
    backoff_state: backoffState,
    reasons,
  };
}

function computeUiLaneDiag(input = {}) {
  const nowMs = Number.isFinite(input.nowMs) ? Number(input.nowMs) : Date.now();
  const staleAfterMs = Math.max(1000, Number(input.staleAfterMs || 120000));
  const activeConnections = Math.max(0, Number(input.activeConnections || 0));
  const lastUiEventTs = Number.isFinite(input.lastUiEventTs) ? Number(input.lastUiEventTs) : null;
  const ageMs = lastUiEventTs == null ? null : Math.max(0, nowMs - lastUiEventTs);
  const stale = activeConnections > 0 && (ageMs == null || ageMs > staleAfterMs);

  return {
    active_connections: activeConnections,
    last_ui_event_ts: lastUiEventTs == null ? null : new Date(lastUiEventTs).toISOString(),
    stale_after_ms: staleAfterMs,
    ui_broadcaster_stale: stale,
    stale_age_ms: ageMs,
  };
}

function classifyUpstreamHealthResponse(input = {}) {
  const statusCode = Number(input.statusCode || 0);
  const contentType = String(input.contentType || '').toLowerCase();
  const bodyText = String(input.bodyText || '');

  if (statusCode < 200 || statusCode >= 300) {
    return {
      ok: false,
      status_code: statusCode,
      content_type: contentType || null,
      reason: 'upstream_status_non_2xx',
    };
  }

  const trimmed = bodyText.trim();
  if (trimmed.toLowerCase() === 'ok') {
    return {
      ok: true,
      status_code: statusCode,
      content_type: contentType || null,
      response_kind: 'plain_ok',
    };
  }

  if (contentType.includes('application/json')) {
    try {
      const parsed = JSON.parse(bodyText);
      if (parsed && typeof parsed === 'object' && parsed.ok === true) {
        return {
          ok: true,
          status_code: statusCode,
          content_type: contentType || null,
          response_kind: 'json_ok',
        };
      }
      return {
        ok: false,
        status_code: statusCode,
        content_type: contentType || null,
        reason: 'json_missing_ok_true',
      };
    } catch (_) {
      return {
        ok: false,
        status_code: statusCode,
        content_type: contentType || null,
        reason: 'json_parse_error',
      };
    }
  }

  if (/<!doctype html>|<html/i.test(trimmed)) {
    return {
      ok: false,
      status_code: statusCode,
      content_type: contentType || null,
      reason: 'html_fallback_not_machine_health',
    };
  }

  return {
    ok: false,
    status_code: statusCode,
    content_type: contentType || null,
    reason: 'non_machine_health_response',
  };
}

function computeReadiness(input = {}) {
  const upstream = input.upstream || { ok: false, reason: 'upstream_not_checked' };
  const telegram = input.telegram || { telegram_lane_locked_out: false };
  const ui = input.ui || { ui_broadcaster_stale: false };
  const runtime = input.runtime || { event_loop_stalled: false };
  const api = input.api || { routes_mounted: true };
  const maintenanceMode = Boolean(input.maintenanceMode);

  const reasons = [];
  if (!api.routes_mounted) reasons.push('api_routes_unavailable');
  if (!upstream.ok) reasons.push(`upstream_unready:${upstream.reason || 'unknown'}`);
  if (!maintenanceMode && telegram.telegram_lane_locked_out) reasons.push('telegram_lane_locked_out');
  if (!maintenanceMode && telegram.telegram_ingest_stale) reasons.push('telegram_ingest_stale');
  if (!maintenanceMode && ui.ui_broadcaster_stale) reasons.push('ui_broadcaster_stale');
  if (!maintenanceMode && runtime.event_loop_stalled) reasons.push('event_loop_stalled');

  return {
    ready: reasons.length === 0,
    maintenance_mode: maintenanceMode,
    reasons,
    components: {
      api,
      upstream,
      telegram,
      ui,
      runtime,
    },
  };
}

class TokenBucket {
  constructor({ ratePerMinute, burst }) {
    this.ratePerMs = Math.max(0, ratePerMinute) / 60000;
    this.capacity = Math.max(1, burst);
    this.tokens = this.capacity;
    this.last = Date.now();
  }

  take(cost = 1) {
    const now = Date.now();
    const elapsed = Math.max(0, now - this.last);
    this.last = now;
    this.tokens = Math.min(this.capacity, this.tokens + elapsed * this.ratePerMs);
    if (this.tokens >= cost) {
      this.tokens -= cost;
      return true;
    }
    return false;
  }
}

function createEdgeServer(options = {}) {
  const env = options.env || process.env;
  const bindHost = String(options.bindHost || env.OPENCLAW_EDGE_BIND || '127.0.0.1');
  const bindPort = Number(options.bindPort || env.OPENCLAW_EDGE_PORT || 18800);
  const upstreamHost = String(options.upstreamHost || env.OPENCLAW_EDGE_UPSTREAM_HOST || '127.0.0.1');
  const upstreamPort = Number(options.upstreamPort || env.OPENCLAW_EDGE_UPSTREAM_PORT || 18789);
  const maxBodyBytes = Number(options.maxBodyBytes || env.OPENCLAW_EDGE_MAX_BODY_BYTES || 256 * 1024);

  const ratePerMinute = Number(options.ratePerMinute || env.OPENCLAW_EDGE_RATE_PER_MIN || 30);
  const burst = Number(options.burst || env.OPENCLAW_EDGE_BURST || 10);

  const strictPerms = process.platform !== 'win32';
  const tokensFile = String(env.OPENCLAW_EDGE_TOKENS_FILE || '').trim();
  const hmacKeysFile = String(env.OPENCLAW_EDGE_HMAC_KEYS_FILE || '').trim();

  // Prefer file-based secrets to avoid env leakage via process listing.
  const tokenMap = parseTokenMap(tokensFile ? readSecretsFile(tokensFile, { strictPerms }) : env.OPENCLAW_EDGE_TOKENS);
  const hmacKeys = parseKeyMap(hmacKeysFile ? readSecretsFile(hmacKeysFile, { strictPerms }) : env.OPENCLAW_EDGE_HMAC_KEYS);
  const hmacSkewSec = Number(env.OPENCLAW_EDGE_HMAC_SKEW_SEC || 60);
  const allowBearerLoopback = String(env.OPENCLAW_EDGE_ALLOW_BEARER_LOOPBACK || '') === '1';
  const upstreamToken = String(env.OPENCLAW_EDGE_UPSTREAM_TOKEN || env.OPENCLAW_GATEWAY_TOKEN || '');
  const readyProbePath = String(env.OPENCLAW_EDGE_READY_PROBE_PATH || '/health');
  const readyProbeTimeoutMs = Math.max(200, Number(env.OPENCLAW_EDGE_READY_PROBE_TIMEOUT_MS || 1500));
  const readyMaintenanceMode = String(env.OPENCLAW_EDGE_MAINTENANCE_MODE || '') === '1';
  const uiStaleAfterMs = Math.max(1000, Number(env.OPENCLAW_EDGE_UI_STALE_AFTER_MS || 120000));
  const uiAutoClearStale = String(env.OPENCLAW_EDGE_UI_AUTOCLEAR_STALE || '1') !== '0';
  const telemetryDmPolicy = String(env.OPENCLAW_EDGE_TELEGRAM_DM_POLICY || env.OPENCLAW_TELEGRAM_DM_POLICY || '');
  const telemetryGroupPolicy = String(env.OPENCLAW_EDGE_TELEGRAM_GROUP_POLICY || env.OPENCLAW_TELEGRAM_GROUP_POLICY || '');
  const telemetryAllowlistRaw = String(env.OPENCLAW_EDGE_TELEGRAM_ALLOWLIST || env.OPENCLAW_TELEGRAM_ALLOWLIST || '');
  const telemetryPairingsRaw = String(env.OPENCLAW_EDGE_TELEGRAM_PAIRINGS || env.OPENCLAW_TELEGRAM_PAIRINGS || '');
  const telemetryTelegramEnabled = String(env.OPENCLAW_EDGE_TELEGRAM_ENABLED || env.OPENCLAW_TELEGRAM_ENABLED || '') === '1';
  const telemetryTelegramStaleMs = Math.max(1000, Number(env.OPENCLAW_EDGE_TELEGRAM_STALE_MS || 300000));
  let telemetryLastTelegramIngestTs = Number.isFinite(Number(env.OPENCLAW_EDGE_LAST_TELEGRAM_INGEST_TS || ''))
    ? Number(env.OPENCLAW_EDGE_LAST_TELEGRAM_INGEST_TS)
    : null;
  let telemetryLastTelegramSendTs = Number.isFinite(Number(env.OPENCLAW_EDGE_LAST_TELEGRAM_SEND_TS || ''))
    ? Number(env.OPENCLAW_EDGE_LAST_TELEGRAM_SEND_TS)
    : null;
  const telemetryTelegramConnected = env.OPENCLAW_EDGE_TELEGRAM_CONNECTED == null
    ? null
    : String(env.OPENCLAW_EDGE_TELEGRAM_CONNECTED) === '1';
  const telemetryTelegramBackoff = env.OPENCLAW_EDGE_TELEGRAM_BACKOFF_STATE || null;

  const maxInflightGlobal = Number(env.OPENCLAW_EDGE_MAX_INFLIGHT_GLOBAL || 32);
  const maxInflightPerIdentity = Number(env.OPENCLAW_EDGE_MAX_INFLIGHT_PER_IDENTITY || 8);
  const headersTimeoutMs = Number(env.OPENCLAW_EDGE_HEADERS_TIMEOUT_MS || 5000);
  const requestTimeoutMs = Number(env.OPENCLAW_EDGE_REQUEST_TIMEOUT_MS || 15000);
  const eventLoopStallMs = Math.max(250, Number(env.OPENCLAW_EDGE_EVENT_LOOP_STALL_MS || 5000));
  const startedAtMs = Date.now();
  let eventLoopLagMs = 0;
  let eventLoopLagMaxMs = 0;
  let eventLoopSamples = 0;
  let eventLoopLastSampleTs = startedAtMs;
  let loopTickExpected = Date.now() + 1000;
  const loopSampler = setInterval(() => {
    const now = Date.now();
    const drift = Math.max(0, now - loopTickExpected);
    eventLoopLagMs = drift;
    eventLoopLagMaxMs = Math.max(eventLoopLagMaxMs, drift);
    eventLoopSamples += 1;
    eventLoopLastSampleTs = now;
    loopTickExpected = now + 1000;
  }, 1000);
  if (typeof loopSampler.unref === 'function') loopSampler.unref();

  const logFn = typeof options.logFn === 'function' ? options.logFn : (line) => process.stdout.write(line + '\n');
  const auditSink =
    options.auditSink ||
    createAuditSink({
      path: env.OPENCLAW_EDGE_AUDIT_PATH,
      rotateBytes: env.OPENCLAW_EDGE_AUDIT_ROTATE_BYTES,
      keep: env.OPENCLAW_EDGE_AUDIT_ROTATE_KEEP,
      hashChain: env.OPENCLAW_EDGE_AUDIT_HASH_CHAIN,
    });

  if (!isLoopbackBind(bindHost)) {
    if (String(env.OPENCLAW_EDGE_BIND_ALLOW_NONLOOPBACK || '') !== '1') {
      const err = new Error('non-loopback bind requires OPENCLAW_EDGE_BIND_ALLOW_NONLOOPBACK=1');
      err.code = 'EDGE_BIND_NONLOOPBACK_NOT_ALLOWED';
      throw err;
    }
  }

  if (tokenMap.size === 0 && hmacKeys.size === 0) {
    const err = new Error('must set OPENCLAW_EDGE_TOKENS and/or OPENCLAW_EDGE_HMAC_KEYS');
    err.code = 'EDGE_NO_AUTH';
    throw err;
  }

  const buckets = new Map(); // identity -> TokenBucket
  let inflightGlobal = 0;
  const inflightByIdentity = new Map(); // identity -> count
  const uiConnections = new Set();
  let lastUiEventTs = null;
  let uiAutoClears = 0;

  function markUiEvent(nowMs = Date.now()) {
    lastUiEventTs = nowMs;
  }

  function clearUiConnections() {
    let closed = 0;
    for (const socket of Array.from(uiConnections)) {
      try {
        socket.destroy();
      } catch (_) {}
      closed += 1;
    }
    uiConnections.clear();
    if (closed > 0) {
      uiAutoClears += 1;
      markUiEvent();
    }
    return closed;
  }

  function buildTelegramDiag() {
    return computeTelegramLaneDiag({
      telegramEnabled: telemetryTelegramEnabled,
      dmPolicy: telemetryDmPolicy,
      groupPolicy: telemetryGroupPolicy,
      allowlist: telemetryAllowlistRaw,
      pairings: telemetryPairingsRaw,
      staleAfterMs: telemetryTelegramStaleMs,
      nowMs: Date.now(),
      lastIngestTs: telemetryLastTelegramIngestTs,
      lastSendTs: telemetryLastTelegramSendTs,
      connected: telemetryTelegramConnected,
      backoffState: telemetryTelegramBackoff,
    });
  }

  function buildUiDiag(nowMs = Date.now()) {
    const diag = computeUiLaneDiag({
      activeConnections: uiConnections.size,
      lastUiEventTs,
      nowMs,
      staleAfterMs: uiStaleAfterMs,
    });
    return {
      ...diag,
      last_broadcast_ts: diag.last_ui_event_ts,
      queue_depth: 0,
      auto_clears: uiAutoClears,
    };
  }

  function buildRuntimeDiag(nowMs = Date.now()) {
    return computeRuntimeDiag({
      nowMs,
      eventLoopLagMs,
      eventLoopLagMaxMs,
      eventLoopSamples,
      eventLoopLastSampleTs,
      eventLoopStallMs,
      inflightGlobal,
      inflightIdentities: inflightByIdentity.size,
    });
  }

  function buildIdentityDiag(envObj = process.env) {
    return {
      repo_sha: envObj.OPENCLAW_REPO_SHA || null,
      repo_branch: envObj.OPENCLAW_REPO_BRANCH || null,
      entrypoint: envObj.OPENCLAW_ENTRYPOINT || null,
    };
  }

  async function probeUpstreamReady() {
    return new Promise((resolve) => {
      const headers = {};
      if (upstreamToken) headers.authorization = `Bearer ${upstreamToken}`;
      const req = http.request(
        {
          host: upstreamHost,
          port: upstreamPort,
          method: 'GET',
          path: readyProbePath,
          headers,
          timeout: readyProbeTimeoutMs,
        },
        (res) => {
          const chunks = [];
          let total = 0;
          res.on('data', (chunk) => {
            if (total > 8192) return;
            total += chunk.length;
            if (total <= 8192) chunks.push(chunk);
          });
          res.on('end', () => {
            const bodyText = Buffer.concat(chunks).toString('utf8');
            const contentType = Array.isArray(res.headers['content-type'])
              ? res.headers['content-type'][0]
              : res.headers['content-type'];
            resolve(
              classifyUpstreamHealthResponse({
                statusCode: res.statusCode || 0,
                contentType: contentType || '',
                bodyText,
              })
            );
          });
        }
      );
      req.on('timeout', () => {
        req.destroy(new Error('ready_probe_timeout'));
      });
      req.on('error', (error) => {
        resolve({
          ok: false,
          reason: 'ready_probe_error',
          error: String(error && error.message ? error.message : error),
        });
      });
      req.end();
    });
  }

  async function buildReadyPayload(meta = {}) {
    const nowMs = Date.now();
    const upstream = await probeUpstreamReady();
    const telegram = buildTelegramDiag();
    const ui = buildUiDiag(nowMs);
    const runtime = buildRuntimeDiag(nowMs);
    let clearedConnections = 0;
    if (uiAutoClearStale && ui.ui_broadcaster_stale) {
      clearedConnections = clearUiConnections();
      if (clearedConnections > 0) {
        audit({
          event_type: 'UI_RECOVERED',
          request_id: meta.requestId || undefined,
          identity: meta.identity || undefined,
          route: safeHeaderString(meta.route || '/ready'),
          method: safeHeaderString(meta.method || 'GET'),
          status: 200,
          closed_connections: clearedConnections,
          stale_age_ms: ui.stale_age_ms == null ? null : ui.stale_age_ms,
        });
      }
    }
    const refreshedUi = buildUiDiag(nowMs);
    if (!readyMaintenanceMode && telegram.enabled && telegram.telegram_ingest_stale) {
      audit({
        event_type: 'TELEGRAM_STALE',
        request_id: meta.requestId || undefined,
        identity: meta.identity || undefined,
        route: safeHeaderString(meta.route || '/ready'),
        method: safeHeaderString(meta.method || 'GET'),
        status: 503,
        stale_age_ms: telegram.telegram_ingest_age_ms == null ? null : telegram.telegram_ingest_age_ms,
        stale_after_ms: telegram.telegram_stale_after_ms,
      });
    }
    if (!readyMaintenanceMode && runtime.event_loop_stalled) {
      audit({
        event_type: 'EVENT_LOOP_STALL',
        request_id: meta.requestId || undefined,
        identity: meta.identity || undefined,
        route: safeHeaderString(meta.route || '/ready'),
        method: safeHeaderString(meta.method || 'GET'),
        status: 503,
        event_loop_lag_ms: runtime.event_loop_lag_ms,
        event_loop_stall_after_ms: runtime.event_loop_stall_after_ms,
      });
    }
    const readiness = computeReadiness({
      api: { routes_mounted: true },
      upstream,
      telegram,
      ui: refreshedUi,
      runtime,
      maintenanceMode: readyMaintenanceMode,
    });
    return {
      ok: readiness.ready,
      readiness,
      cleared_ui_connections: clearedConnections,
      timestamp_utc: nowUtcIso(),
    };
  }

  function bucketFor(identity) {
    if (!buckets.has(identity)) {
      buckets.set(identity, new TokenBucket({ ratePerMinute, burst }));
    }
    return buckets.get(identity);
  }

  function audit(event) {
    // Ensure we never log Authorization or bodies.
    const clean = {
      ts_utc: nowUtcIso(),
      ...event
    };
    const line = JSON.stringify(clean);
    if (line.includes('Bearer ')) {
      // Fail-closed: never emit potentially sensitive text.
      return;
    }
    logFn(line);
    try {
      auditSink.writeLine(line);
    } catch (_) {
      // Fail-open on audit sink errors (console audit line already emitted).
    }
  }

  function deny(res, statusCode, code) {
    res.statusCode = statusCode;
    res.setHeader('content-type', 'application/json; charset=utf-8');
    res.end(JSON.stringify({ ok: false, error: code }) + '\n');
  }

  function incInflight(identity) {
    const id = String(identity || 'anonymous');
    const per = inflightByIdentity.get(id) || 0;
    if (inflightGlobal + 1 > maxInflightGlobal) return { ok: false, id, scope: 'global' };
    if (per + 1 > maxInflightPerIdentity) return { ok: false, id, scope: 'identity' };
    inflightGlobal += 1;
    inflightByIdentity.set(id, per + 1);
    return { ok: true, id };
  }

  function decInflight(id) {
    if (!id) return;
    const per = inflightByIdentity.get(id) || 0;
    if (per <= 1) inflightByIdentity.delete(id);
    else inflightByIdentity.set(id, per - 1);
    inflightGlobal = Math.max(0, inflightGlobal - 1);
  }

  function getTestDelayMs() {
    if (process.env.NODE_ENV !== 'test') return 0;
    const ms = Number(process.env.OPENCLAW_EDGE_TEST_DELAY_MS || 0);
    return Number.isFinite(ms) && ms > 0 ? ms : 0;
  }

  function routePolicy(req) {
    const method = String(req.method || 'GET').toUpperCase();
    let pathname = '/';
    try {
      // URL constructor requires an origin; any local placeholder is fine.
      pathname = new URL(String(req.url || '/'), 'http://edge.local').pathname || '/';
    } catch (_) {}

    if (method === 'GET' && (pathname === '/health' || pathname === '/status')) {
      return { decision: 'allow', action: 'read_health', pathname };
    }
    if (method === 'GET' && pathname === '/diag/runtime') {
      return { decision: 'allow', action: 'diag_runtime', pathname };
    }
    if (method === 'GET' && pathname === '/ready') {
      return { decision: 'allow', action: 'read_ready', pathname };
    }
    if (method === 'GET' && pathname === '/diag') {
      return { decision: 'allow', action: 'diag_all', pathname };
    }
    if (method === 'GET' && pathname === '/diag/telegram') {
      return { decision: 'allow', action: 'diag_telegram', pathname };
    }
    if (method === 'GET' && pathname === '/diag/ui') {
      return { decision: 'allow', action: 'diag_ui', pathname };
    }
    if (method === 'GET' && pathname === '/diag/routes') {
      return { decision: 'allow', action: 'diag_routes', pathname };
    }
    if (pathname.startsWith('/api/')) {
      return { decision: 'allow', action: 'api_not_found', pathname };
    }
    if (
      method === 'OPTIONS'
      && (
        pathname === '/health'
        || pathname === '/status'
        || pathname === '/ready'
        || pathname === '/diag'
        || pathname === '/diag/runtime'
        || pathname === '/diag/telegram'
        || pathname === '/diag/ui'
        || pathname === '/diag/routes'
        || pathname.startsWith('/api/')
        || pathname.startsWith('/rpc/')
      )
    ) {
      return { decision: 'allow', action: 'preflight', pathname };
    }
    if (method === 'POST' && pathname.startsWith('/rpc/')) {
      return { decision: 'require_approval', action: 'gateway_rpc', pathname };
    }
    return { decision: 'deny', action: 'deny', pathname };
  }

  function extractHmacHeaders(req) {
    const tsHdr = req.headers['x-openclaw-timestamp'];
    const kidHdr = req.headers['x-openclaw-keyid'];
    const sigHdr = req.headers['x-openclaw-signature'];
    const ts = Array.isArray(tsHdr) ? tsHdr[0] : tsHdr ? String(tsHdr) : '';
    const keyId = Array.isArray(kidHdr) ? kidHdr[0] : kidHdr ? String(kidHdr) : '';
    const sig = Array.isArray(sigHdr) ? sigHdr[0] : sigHdr ? String(sigHdr) : '';
    return { ts, keyId, sig };
  }

  function verifyHmac({ req, body }) {
    const { ts, keyId, sig } = extractHmacHeaders(req);
    if (!ts || !keyId || !sig) return { ok: false };
    const secret = hmacKeys.get(String(keyId));
    if (!secret) return { ok: false };

    const tsNum = Number(ts);
    if (!Number.isFinite(tsNum)) return { ok: false };
    const nowSec = Math.floor(Date.now() / 1000);
    if (Math.abs(nowSec - tsNum) > Math.max(1, hmacSkewSec)) return { ok: false };

    const method = String(req.method || 'GET').toUpperCase();
    const path = String(req.url || '/');
    const bodyHash = sha256Hex(body || Buffer.alloc(0));
    const msg = `${method}\n${path}\n${String(tsNum)}\n${bodyHash}`;
    const expected = hmacHex(secret, msg);
    if (!safeTimingEqualHex(expected, sig)) return { ok: false };
    return { ok: true, identity: String(keyId) };
  }

  const server = http.createServer((req, res) => {
    const requestId = randomUUID();
    const started = Date.now();

    const policy = routePolicy(req);
    const machineRoute = isMachineRoutePath(policy.pathname || '/');
    if (policy.decision === 'deny') {
      audit({
        event_type: 'edge_route_denied',
        request_id: requestId,
        route: safeHeaderString(policy.pathname || '/'),
        method: safeHeaderString(req.method || 'GET'),
        status: 404
      });
      return deny(res, 404, 'not_found');
    }

    const bearer = extractBearer(req);
    const bearerIdentity = bearer && tokenMap.has(bearer) ? tokenMap.get(bearer) : null;
    const remoteAddr = req.socket && req.socket.remoteAddress;
    const isLoopback = isLoopbackRemote(remoteAddr);

    // Buffer body (bounded) to enforce size limits and to enable HMAC verification.
    const chunks = [];
    let total = 0;
    let tooLarge = false;
    req.on('data', (buf) => {
      if (tooLarge) {
        return;
      }
      total += buf.length;
      if (total > maxBodyBytes) {
        tooLarge = true;

        audit({
          event_type: 'edge_body_too_large',
          request_id: requestId,
          identity: bearerIdentity || undefined,
          route: safeHeaderString(policy.pathname || '/'),
          method: safeHeaderString(req.method || 'GET'),
          status: 413,
          bytes: total
        });
        deny(res, 413, 'payload_too_large');

        // Drain remaining body bytes (best-effort) but do not buffer.
        try {
          req.removeAllListeners('end');
          req.on('data', () => {});
          req.on('end', () => {});
        } catch (_) {}
        return;
      }
      chunks.push(buf);
    });

    req.on('end', async () => {
      if (tooLarge) return;
      const body = chunks.length ? Buffer.concat(chunks) : null;

      // Authenticate: either HMAC (when configured/required) or Bearer (loopback-only option).
      let identity = null;
      if (hmacKeys.size > 0) {
        const verified = verifyHmac({ req, body });
        if (verified.ok) {
          identity = verified.identity;
        } else if (isLoopback && allowBearerLoopback && bearerIdentity) {
          identity = bearerIdentity;
        }
      } else {
        identity = bearerIdentity;
      }

      if (!identity) {
        audit({
          event_type: 'edge_auth_denied',
          request_id: requestId,
          route: safeHeaderString(policy.pathname || '/'),
          method: safeHeaderString(req.method || 'GET'),
          status: 401
        });
        return deny(res, 401, 'unauthorized');
      }

      const inflight = incInflight(identity);
      if (!inflight.ok) {
        audit({
          event_type: 'edge_busy',
          request_id: requestId,
          identity,
          route: safeHeaderString(policy.pathname || '/'),
          method: safeHeaderString(req.method || 'GET'),
          status: 429,
          scope: inflight.scope
        });
        return deny(res, 429, 'busy');
      }

      const inflightId = inflight.id;
      let finished = false;
      function finishOnce() {
        if (finished) return;
        finished = true;
        decInflight(inflightId);
      }
      res.on('finish', finishOnce);
      res.on('close', finishOnce);
      req.on('aborted', finishOnce);

      function failMachineRouteInvariant(contentType, source) {
        audit({
          event_type: 'edge_machine_route_invariant_violation',
          severity: 'fatal',
          request_id: requestId,
          identity,
          route: safeHeaderString(policy.pathname || '/'),
          method: safeHeaderString(req.method || 'GET'),
          status: 500,
          source: safeHeaderString(source || 'response'),
          offending_content_type: safeHeaderString(contentType || ''),
        });
        if (!res.writableEnded) {
          res.statusCode = 500;
          res.setHeader('content-type', 'application/json; charset=utf-8');
          res.end(JSON.stringify({ ok: false, error: 'invariant_violation' }) + '\n');
        }
        finishOnce();
      }

      if (!bucketFor(identity).take(1)) {
        audit({
          event_type: 'edge_rate_limited',
          request_id: requestId,
          identity,
          route: safeHeaderString(policy.pathname || '/'),
          method: safeHeaderString(req.method || 'GET'),
          status: 429
        });
        res.setHeader('retry-after', '60');
        finishOnce();
        return deny(res, 429, 'rate_limited');
      }

      const ctx = classifyRequest({ source: 'http_edge', identity: identity || undefined });
      const approveHeader = req.headers['x-openclaw-approve'];
      const approveToken = Array.isArray(approveHeader) ? approveHeader[0] : approveHeader ? String(approveHeader) : '';

      if (policy.decision === 'require_approval') {
        try {
          requireApproval('gateway_rpc_broad', ctx, { approveToken, env, allowOperatorEnv: false });
        } catch (error) {
          const status = approvalStatusFromError(error);
          audit({
            event_type: 'edge_approval_denied',
            request_id: requestId,
            identity,
            route: safeHeaderString(policy.pathname || '/'),
            method: safeHeaderString(req.method || 'GET'),
            status
          });
          finishOnce();
          return deny(res, status, 'approval_required');
        }

        if (body && isJsonContentType(req)) {
          let parsed = null;
          try {
            parsed = JSON.parse(body.toString('utf8'));
          } catch (_) {
            parsed = null;
          }
          if (parsed) {
            const malformed = detectMalformedReadToolCall(parsed);
            if (malformed) {
              audit({
                event_type: 'edge_rpc_payload_denied',
                request_id: requestId,
                identity,
                route: safeHeaderString(policy.pathname || '/'),
                method: safeHeaderString(req.method || 'GET'),
                status: 400,
                reason: malformed.reason,
                policy_ref: 'tool_governance.rpc_payload.read_requires_path'
              });
              finishOnce();
              return deny(res, 400, 'malformed_rpc_payload');
            }
          }
        }
      }

      if (
        policy.action === 'read_health'
        || policy.action === 'read_ready'
        || policy.action === 'diag_all'
        || policy.action === 'diag_runtime'
        || policy.action === 'diag_telegram'
        || policy.action === 'diag_ui'
        || policy.action === 'diag_routes'
        || policy.action === 'api_not_found'
      ) {
        const nowMs = Date.now();
        const telegramDiag = buildTelegramDiag();
        const uiDiag = buildUiDiag(nowMs);

        if (policy.action === 'read_health') {
          const runtimeDiag = buildRuntimeDiag(nowMs);
          const payload = {
            ok: true,
            alive: true,
            event_loop_active: !runtimeDiag.event_loop_stalled,
            edge_uptime_ms: Math.max(0, nowMs - startedAtMs),
            timestamp_utc: nowUtcIso(),
          };
          res.statusCode = 200;
          res.setHeader('content-type', 'application/json; charset=utf-8');
          res.end(JSON.stringify(payload) + '\n');
          audit({
            event_type: 'edge_health',
            request_id: requestId,
            identity,
            route: safeHeaderString(policy.pathname || '/'),
            method: safeHeaderString(req.method || 'GET'),
            status: 200,
            latency_ms: Date.now() - started,
          });
          finishOnce();
          return;
        }

        if (policy.action === 'diag_runtime') {
          const runtimeDiag = buildRuntimeDiag(nowMs);
          const buildDiag = buildIdentityDiag(env);
          const payload = {
            ok: true,
            diag: {
              uptime_ms: Math.max(0, nowMs - startedAtMs),
              ...runtimeDiag,
              runtime: { build: buildDiag },
            },
            build: buildDiag,
            timestamp_utc: nowUtcIso(),
          };
          res.statusCode = 200;
          res.setHeader('content-type', 'application/json; charset=utf-8');
          res.end(JSON.stringify(payload) + '\n');
          audit({
            event_type: 'edge_diag',
            request_id: requestId,
            identity,
            route: safeHeaderString(policy.pathname || '/'),
            method: safeHeaderString(req.method || 'GET'),
            status: 200,
            latency_ms: Date.now() - started,
          });
          finishOnce();
          return;
        }

        if (policy.action === 'diag_telegram') {
          const payload = {
            ok: true,
            diag: telegramDiag,
            timestamp_utc: nowUtcIso(),
          };
          res.statusCode = 200;
          res.setHeader('content-type', 'application/json; charset=utf-8');
          res.end(JSON.stringify(payload) + '\n');
          audit({
            event_type: 'edge_diag',
            request_id: requestId,
            identity,
            route: safeHeaderString(policy.pathname || '/'),
            method: safeHeaderString(req.method || 'GET'),
            status: 200,
            latency_ms: Date.now() - started,
          });
          finishOnce();
          return;
        }

        if (policy.action === 'diag_ui') {
          const payload = {
            ok: true,
            diag: uiDiag,
            timestamp_utc: nowUtcIso(),
          };
          res.statusCode = 200;
          res.setHeader('content-type', 'application/json; charset=utf-8');
          res.end(JSON.stringify(payload) + '\n');
          audit({
            event_type: 'edge_diag',
            request_id: requestId,
            identity,
            route: safeHeaderString(policy.pathname || '/'),
            method: safeHeaderString(req.method || 'GET'),
            status: 200,
            latency_ms: Date.now() - started,
          });
          finishOnce();
          return;
        }

        if (policy.action === 'diag_routes') {
          const payload = {
            ok: true,
            routes: [
              '/health',
              '/status',
              '/ready',
              '/diag',
              '/diag/runtime',
              '/diag/telegram',
              '/diag/ui',
              '/diag/routes',
              '/api/*',
              '/rpc/*'
            ],
          };
          res.statusCode = 200;
          res.setHeader('content-type', 'application/json; charset=utf-8');
          res.end(JSON.stringify(payload) + '\n');
          audit({
            event_type: 'edge_diag',
            request_id: requestId,
            identity,
            route: safeHeaderString(policy.pathname || '/'),
            method: safeHeaderString(req.method || 'GET'),
            status: 200,
            latency_ms: Date.now() - started,
          });
          finishOnce();
          return;
        }

        if (policy.action === 'diag_all') {
          const runtimeDiag = buildRuntimeDiag(nowMs);
          const upstream = await probeUpstreamReady();
          const payload = {
            ok: true,
            diag: {
              runtime: { uptime_ms: Math.max(0, nowMs - startedAtMs), ...runtimeDiag },
              upstream,
              telegram: telegramDiag,
              ui: uiDiag,
            },
            timestamp_utc: nowUtcIso(),
          };
          res.statusCode = 200;
          res.setHeader('content-type', 'application/json; charset=utf-8');
          res.end(JSON.stringify(payload) + '\n');
          audit({
            event_type: 'edge_diag',
            request_id: requestId,
            identity,
            route: safeHeaderString(policy.pathname || '/'),
            method: safeHeaderString(req.method || 'GET'),
            status: 200,
            latency_ms: Date.now() - started,
          });
          finishOnce();
          return;
        }

        if (policy.action === 'read_ready') {
          const payload = await buildReadyPayload({
            requestId,
            identity,
            method: String(req.method || 'GET'),
            route: policy.pathname || '/ready',
          });
          res.statusCode = payload.ok ? 200 : 503;
          res.setHeader('content-type', 'application/json; charset=utf-8');
          res.end(JSON.stringify(payload) + '\n');
          audit({
            event_type: 'edge_ready',
            request_id: requestId,
            identity,
            route: safeHeaderString(policy.pathname || '/'),
            method: safeHeaderString(req.method || 'GET'),
            status: res.statusCode,
            latency_ms: Date.now() - started,
            reasons: payload.readiness && Array.isArray(payload.readiness.reasons) ? payload.readiness.reasons : [],
          });
          finishOnce();
          return;
        }

        if (policy.action === 'api_not_found') {
          res.statusCode = 404;
          res.setHeader('content-type', 'application/json; charset=utf-8');
          res.end(JSON.stringify({ ok: false, error: 'api_not_found' }) + '\n');
          audit({
            event_type: 'edge_api_not_found',
            request_id: requestId,
            identity,
            route: safeHeaderString(policy.pathname || '/'),
            method: safeHeaderString(req.method || 'GET'),
            status: 404,
            latency_ms: Date.now() - started,
          });
          finishOnce();
          return;
        }
      }

      // OPTIONS requests never proxy upstream.
      if (String(req.method || 'GET').toUpperCase() === 'OPTIONS') {
        res.statusCode = 204;
        res.setHeader('cache-control', 'no-store');
        res.end();
        audit({
          event_type: 'edge_request',
          request_id: requestId,
          identity,
          route: safeHeaderString(policy.pathname || '/'),
          method: safeHeaderString(req.method || 'GET'),
          status: 204,
          latency_ms: Date.now() - started
        });
        finishOnce();
        return;
      }

      const delayMs = getTestDelayMs();
      if (delayMs > 0) {
        setTimeout(proxyUpstream, delayMs);
        return;
      }

      proxyUpstream();

      function proxyUpstream() {
      const upstreamHeaders = { ...req.headers };
      delete upstreamHeaders.host;
      // Do not forward edge client authorization header.
      delete upstreamHeaders.authorization;
      delete upstreamHeaders['x-openclaw-approve'];
      delete upstreamHeaders['x-openclaw-keyid'];
      delete upstreamHeaders['x-openclaw-timestamp'];
      delete upstreamHeaders['x-openclaw-signature'];

      if (upstreamToken) {
        upstreamHeaders.authorization = `Bearer ${upstreamToken}`;
      }

      const upstreamReq = http.request(
        {
          host: upstreamHost,
          port: upstreamPort,
          method: req.method,
          path: req.url,
          headers: upstreamHeaders,
          timeout: 60000
        },
        (upstreamRes) => {
          const upstreamContentType = Array.isArray(upstreamRes.headers && upstreamRes.headers['content-type'])
            ? upstreamRes.headers['content-type'].join(', ')
            : upstreamRes.headers && upstreamRes.headers['content-type'];
          if (machineRoute && hasHtmlContentType(upstreamContentType)) {
            upstreamRes.resume();
            failMachineRouteInvariant(upstreamContentType, 'upstream_response');
            return;
          }
          res.statusCode = upstreamRes.statusCode || 502;
          for (const [k, v] of Object.entries(upstreamRes.headers || {})) {
            // Avoid forwarding hop-by-hop headers; keep minimal.
            if (!k) continue;
            if (k.toLowerCase() === 'transfer-encoding') continue;
            res.setHeader(k, v);
          }

          upstreamRes.on('data', (d) => res.write(d));
          upstreamRes.on('end', () => {
            res.end();
            if (String(req.url || '').startsWith('/rpc/')) {
              markUiEvent();
              const path = String(req.url || '').toLowerCase();
              const bodyText = body ? body.toString('utf8').toLowerCase() : '';
              if (path.includes('telegram') || bodyText.includes('telegram')) {
                telemetryLastTelegramSendTs = Date.now();
              }
            }
            audit({
              event_type: 'edge_request',
              request_id: requestId,
              identity,
              route: safeHeaderString(policy.pathname || '/'),
              method: safeHeaderString(req.method || 'GET'),
              status: res.statusCode,
              latency_ms: Date.now() - started
            });
            finishOnce();
          });
        }
      );

      upstreamReq.on('timeout', () => {
        upstreamReq.destroy(new Error('upstream timeout'));
      });

      upstreamReq.on('error', () => {
        if (!res.headersSent) {
          deny(res, 502, 'upstream_error');
        } else {
          try { res.end(); } catch (_) {}
        }
        audit({
          event_type: 'edge_upstream_error',
          request_id: requestId,
          identity,
          route: safeHeaderString(req.url || '/'),
          method: safeHeaderString(req.method || 'GET'),
          status: 502,
          latency_ms: Date.now() - started
        });
        finishOnce();
      });

      if (body) upstreamReq.write(body);
      upstreamReq.end();
      }
    });
  });

  server.headersTimeout = headersTimeoutMs;
  server.requestTimeout = requestTimeoutMs;

  server.on('upgrade', (req, socket, head) => {
    const requestId = randomUUID();
    const started = Date.now();

    let pathname = '/';
    try {
      pathname = new URL(String(req.url || '/'), 'http://edge.local').pathname || '/';
    } catch (_) {}

    if (!pathname.startsWith('/rpc/')) {
      audit({
        event_type: 'edge_ws_route_denied',
        request_id: requestId,
        route: safeHeaderString(pathname || '/'),
        status: 404
      });
      socket.write('HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n');
      socket.destroy();
      return;
    }

    const bearer = extractBearer(req);
    const bearerIdentity = bearer && tokenMap.has(bearer) ? tokenMap.get(bearer) : null;
    const remoteAddr = req.socket && req.socket.remoteAddress;
    const isLoopback = isLoopbackRemote(remoteAddr);
    let identity = null;

    // For websocket upgrades, require approval and authenticate.
    // In HMAC mode, require HMAC unless loopback+allowBearerLoopback.
    if (hmacKeys.size > 0) {
      // WebSocket upgrade requests have no meaningful HTTP body; sign with empty body hash.
      const verified = verifyHmac({ req, body: Buffer.alloc(0) });
      if (verified.ok) {
        identity = verified.identity;
      } else if (isLoopback && allowBearerLoopback && bearerIdentity) {
        identity = bearerIdentity;
      }
    } else {
      identity = bearerIdentity;
    }

    const ctx = classifyRequest({ source: 'http_edge', identity: identity || undefined });

    if (!identity) {
      audit({
        event_type: 'edge_ws_auth_denied',
        request_id: requestId,
        route: safeHeaderString(pathname || '/'),
        status: 401
      });
      socket.write('HTTP/1.1 401 Unauthorized\r\nConnection: close\r\n\r\n');
      socket.destroy();
      return;
    }

    const inflight = incInflight(identity);
    if (!inflight.ok) {
      audit({
        event_type: 'edge_ws_busy',
        request_id: requestId,
        identity,
        route: safeHeaderString(pathname || '/'),
        status: 429,
        scope: inflight.scope
      });
      socket.write('HTTP/1.1 429 Too Many Requests\r\nConnection: close\r\nRetry-After: 60\r\n\r\n');
      socket.destroy();
      return;
    }

    const inflightId = inflight.id;
    let wsFinished = false;
    function wsFinishOnce() {
      if (wsFinished) return;
      wsFinished = true;
      uiConnections.delete(socket);
      decInflight(inflightId);
    }
    uiConnections.add(socket);
    markUiEvent();
    socket.on('close', wsFinishOnce);
    socket.on('error', wsFinishOnce);

    if (!bucketFor(identity).take(1)) {
      audit({
        event_type: 'edge_ws_rate_limited',
        request_id: requestId,
        identity,
        route: safeHeaderString(pathname || '/'),
        status: 429
      });
      socket.write('HTTP/1.1 429 Too Many Requests\r\nConnection: close\r\nRetry-After: 60\r\n\r\n');
      socket.destroy();
      wsFinishOnce();
      return;
    }

    // WebSocket can invoke broad RPC; require ask-first approval by default.
    const approveHeader = req.headers['x-openclaw-approve'];
    const approveToken = Array.isArray(approveHeader) ? approveHeader[0] : approveHeader ? String(approveHeader) : '';
    try {
      requireApproval('gateway_rpc_broad', ctx, { approveToken, env, allowOperatorEnv: false });
    } catch (error) {
      const statusLine = approvalStatusFromError(error) === 403
        ? 'HTTP/1.1 403 Forbidden'
        : 'HTTP/1.1 500 Internal Server Error';
      audit({
        event_type: 'edge_ws_approval_denied',
        request_id: requestId,
        identity,
        route: safeHeaderString(pathname || '/'),
        status: 403,
        latency_ms: Date.now() - started
      });
      socket.write(statusLine + '\r\nConnection: close\r\n\r\n');
      socket.destroy();
      wsFinishOnce();
      return;
    }

    const upstream = net.connect({ host: upstreamHost, port: upstreamPort }, () => {
      const upstreamHeaders = { ...req.headers };
      delete upstreamHeaders.host;
      // Do not forward edge client authorization header.
      delete upstreamHeaders.authorization;
      delete upstreamHeaders['x-openclaw-approve'];
      if (upstreamToken) {
        upstreamHeaders.authorization = `Bearer ${upstreamToken}`;
      }

      // Reconstruct the HTTP upgrade request.
      let headerLines = `${req.method} ${req.url} HTTP/1.1\r\n`;
      for (const [k, v] of Object.entries(upstreamHeaders)) {
        if (!k) continue;
        if (v == null) continue;
        headerLines += `${k}: ${Array.isArray(v) ? v.join(', ') : String(v)}\r\n`;
      }
      headerLines += '\r\n';

      upstream.write(headerLines, 'utf8');
      if (head && head.length) upstream.write(head);

      // Pipe both directions.
      socket.on('data', () => markUiEvent());
      upstream.on('data', () => markUiEvent());
      socket.pipe(upstream);
      upstream.pipe(socket);
    });

    upstream.on('error', () => {
      try {
        socket.write('HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\n\r\n');
      } catch (_) {}
      socket.destroy();
      audit({
        event_type: 'edge_ws_upstream_error',
        request_id: requestId,
        identity,
        route: safeHeaderString(pathname || '/'),
        status: 502,
        latency_ms: Date.now() - started
      });
      wsFinishOnce();
    });
  });

  return {
    bindHost,
    bindPort,
    upstreamHost,
    upstreamPort,
    server,
    close: () => new Promise((resolve) => {
      try { clearInterval(loopSampler); } catch (_) {}
      server.close(() => resolve());
    })
  };
}

async function main() {
  const edge = createEdgeServer();
  edge.server.listen(edge.bindPort, edge.bindHost, () => {
    // Do not print tokens or headers; just bind details.
    process.stdout.write(
      `edge_listening host=${edge.bindHost} port=${edge.bindPort} upstream=${edge.upstreamHost}:${edge.upstreamPort}\n`
    );
  });
}

if (require.main === module) {
  main().catch((err) => {
    process.stderr.write(String(err && err.message ? err.message : err) + '\n');
    process.exit(1);
  });
}

module.exports = {
  createEdgeServer,
  parseTokenMap,
  parseKeyMap,
  _test: {
    approvalStatusFromError,
    detectMalformedReadToolCall,
    isMachineRoutePath,
    hasHtmlContentType,
    shouldServeSpaFallback,
    computeRuntimeDiag,
    computeTelegramLaneDiag,
    computeUiLaneDiag,
    classifyUpstreamHealthResponse,
    computeReadiness,
  }
};
