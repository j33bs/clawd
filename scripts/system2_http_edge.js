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

  const maxInflightGlobal = Number(env.OPENCLAW_EDGE_MAX_INFLIGHT_GLOBAL || 32);
  const maxInflightPerIdentity = Number(env.OPENCLAW_EDGE_MAX_INFLIGHT_PER_IDENTITY || 8);
  const headersTimeoutMs = Number(env.OPENCLAW_EDGE_HEADERS_TIMEOUT_MS || 5000);
  const requestTimeoutMs = Number(env.OPENCLAW_EDGE_REQUEST_TIMEOUT_MS || 15000);

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
      return { decision: 'allow', action: 'read_status', pathname };
    }
    if (method === 'OPTIONS' && (pathname === '/health' || pathname === '/status' || pathname.startsWith('/rpc/'))) {
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

    req.on('end', () => {
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
      decInflight(inflightId);
    }
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
    close: () => new Promise((resolve) => server.close(() => resolve()))
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
    approvalStatusFromError
  }
};
