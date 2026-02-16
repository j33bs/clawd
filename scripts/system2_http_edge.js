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
const { randomUUID } = require('node:crypto');

const { classifyRequest } = require('../core/system2/security/trust_boundary');
const { requireApproval, ApprovalRequiredError } = require('../core/system2/security/ask_first');

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

  const tokenMap = parseTokenMap(env.OPENCLAW_EDGE_TOKENS);
  const upstreamToken = String(env.OPENCLAW_EDGE_UPSTREAM_TOKEN || env.OPENCLAW_GATEWAY_TOKEN || '');

  const logFn = typeof options.logFn === 'function' ? options.logFn : (line) => process.stdout.write(line + '\n');

  if (tokenMap.size === 0) {
    const err = new Error('OPENCLAW_EDGE_TOKENS must be set (label:token,...)');
    err.code = 'EDGE_NO_TOKENS';
    throw err;
  }

  const buckets = new Map(); // identity -> TokenBucket

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
  }

  function deny(res, statusCode, code) {
    res.statusCode = statusCode;
    res.setHeader('content-type', 'application/json; charset=utf-8');
    res.end(JSON.stringify({ ok: false, error: code }) + '\n');
  }

  function isBroadHttpRequest(req) {
    const method = String(req.method || 'GET').toUpperCase();
    if (method === 'GET' || method === 'HEAD' || method === 'OPTIONS') return false;
    return true;
  }

  const server = http.createServer((req, res) => {
    const requestId = randomUUID();
    const started = Date.now();

    const bearer = extractBearer(req);
    const identity = bearer && tokenMap.has(bearer) ? tokenMap.get(bearer) : null;
    const ctx = classifyRequest({ source: 'http_edge', identity: identity || undefined });

    if (!identity) {
      audit({
        event_type: 'edge_auth_denied',
        request_id: requestId,
        route: safeHeaderString(req.url || '/'),
        method: safeHeaderString(req.method || 'GET'),
        status: 401
      });
      return deny(res, 401, 'unauthorized');
    }

    if (!bucketFor(identity).take(1)) {
      audit({
        event_type: 'edge_rate_limited',
        request_id: requestId,
        identity,
        route: safeHeaderString(req.url || '/'),
        method: safeHeaderString(req.method || 'GET'),
        status: 429
      });
      res.setHeader('retry-after', '60');
      return deny(res, 429, 'rate_limited');
    }

    const approveHeader = req.headers['x-openclaw-approve'];
    const approveToken = Array.isArray(approveHeader) ? approveHeader[0] : approveHeader ? String(approveHeader) : '';

    if (isBroadHttpRequest(req)) {
      try {
        requireApproval('gateway_rpc_broad', ctx, { approveToken, env });
      } catch (error) {
        const status = error && error.code === 'APPROVAL_REQUIRED' ? 403 : 500;
        audit({
          event_type: 'edge_approval_denied',
          request_id: requestId,
          identity,
          route: safeHeaderString(req.url || '/'),
          method: safeHeaderString(req.method || 'GET'),
          status
        });
        return deny(res, status, 'approval_required');
      }
    }

    // Buffer body (bounded) to enforce size limits and avoid streaming bodies into logs.
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

        // Respond without destroying the underlying socket (avoid client-side hangups).
        audit({
          event_type: 'edge_body_too_large',
          request_id: requestId,
          identity,
          route: safeHeaderString(req.url || '/'),
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
      const upstreamHeaders = { ...req.headers };
      delete upstreamHeaders.host;
      // Do not forward edge client authorization header.
      delete upstreamHeaders.authorization;
      delete upstreamHeaders['x-openclaw-approve'];

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
              route: safeHeaderString(req.url || '/'),
              method: safeHeaderString(req.method || 'GET'),
              status: res.statusCode,
              latency_ms: Date.now() - started
            });
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
      });

      if (body) upstreamReq.write(body);
      upstreamReq.end();
    });
  });

  server.on('upgrade', (req, socket, head) => {
    const requestId = randomUUID();
    const started = Date.now();

    const bearer = extractBearer(req);
    const identity = bearer && tokenMap.has(bearer) ? tokenMap.get(bearer) : null;
    const ctx = classifyRequest({ source: 'http_edge', identity: identity || undefined });

    if (!identity) {
      audit({
        event_type: 'edge_ws_auth_denied',
        request_id: requestId,
        route: safeHeaderString(req.url || '/'),
        status: 401
      });
      socket.write('HTTP/1.1 401 Unauthorized\r\nConnection: close\r\n\r\n');
      socket.destroy();
      return;
    }

    if (!bucketFor(identity).take(1)) {
      audit({
        event_type: 'edge_ws_rate_limited',
        request_id: requestId,
        identity,
        route: safeHeaderString(req.url || '/'),
        status: 429
      });
      socket.write('HTTP/1.1 429 Too Many Requests\r\nConnection: close\r\nRetry-After: 60\r\n\r\n');
      socket.destroy();
      return;
    }

    // WebSocket can invoke broad RPC; require ask-first approval by default.
    const approveHeader = req.headers['x-openclaw-approve'];
    const approveToken = Array.isArray(approveHeader) ? approveHeader[0] : approveHeader ? String(approveHeader) : '';
    try {
      requireApproval('gateway_rpc_broad', ctx, { approveToken, env });
    } catch (error) {
      const statusLine = error instanceof ApprovalRequiredError ? 'HTTP/1.1 403 Forbidden' : 'HTTP/1.1 500 Internal Server Error';
      audit({
        event_type: 'edge_ws_approval_denied',
        request_id: requestId,
        identity,
        route: safeHeaderString(req.url || '/'),
        status: 403,
        latency_ms: Date.now() - started
      });
      socket.write(statusLine + '\r\nConnection: close\r\n\r\n');
      socket.destroy();
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
        route: safeHeaderString(req.url || '/'),
        status: 502,
        latency_ms: Date.now() - started
      });
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
  parseTokenMap
};
