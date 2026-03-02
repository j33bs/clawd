import http from 'node:http';

import { appendContractSignal } from './contract_signal.mjs';

const INSTALL_KEY = '__openclaw_contract_ingress_hook_installed';
const PATCHED_CREATE_KEY = '__openclaw_contract_ingress_create_patched';
const PATCHED_EMIT_KEY = '__openclaw_contract_ingress_emit_patched';

function parsePorts(raw) {
  const inputRaw = raw == null ? '18789,18791,18792' : String(raw);
  if (!inputRaw.trim()) {
    return new Set();
  }
  const input = inputRaw;
  const ports = new Set();
  for (const token of input.split(',')) {
    const trimmed = token.trim();
    if (!trimmed) continue;
    const parsed = Number(trimmed);
    if (Number.isInteger(parsed) && parsed > 0) {
      ports.add(parsed);
    }
  }
  return ports;
}

function isInteractivePath(urlValue) {
  const path = String(urlValue || '');
  return (
    path === '/'
    || path.startsWith('/api')
    || path.startsWith('/rpc/')
    || path.startsWith('/control')
    || path.startsWith('/dashboard')
  );
}

function shouldEmit(req) {
  try {
    if (!req) return false;
    const method = String(req.method || 'GET').toUpperCase();
    if (method === 'OPTIONS') return false;

    if (!isInteractivePath(req.url || '/')) return false;

    const ports = parsePorts(process.env.OPENCLAW_CONTRACT_INGRESS_PORTS);
    if (ports.size === 0) return true;

    const localPort = Number(req.socket?.localPort);
    if (!Number.isInteger(localPort) || localPort <= 0) return false;
    return ports.has(localPort);
  } catch {
    return false;
  }
}

function emitSignal(req) {
  try {
    appendContractSignal('service_request', {
      source: 'gateway_http_ingress',
      method: String(req?.method || 'GET').toUpperCase(),
      path: String(req?.url || '/'),
      port: Number(req?.socket?.localPort) || null,
      host: String(req?.headers?.host || ''),
      ua_present: Boolean(req?.headers?.['user-agent']),
    });
  } catch {
    // fail-open
  }
}

function attachListener(server) {
  try {
    server.on('request', (req) => {
      if (shouldEmit(req)) {
        emitSignal(req);
      }
    });
  } catch {
    // fail-open
  }
}

export function installHttpIngressContractSignal({ logger = null } = {}) {
  try {
    const enabledRaw = String(process.env.OPENCLAW_CONTRACT_INGRESS_SIGNAL || '').trim();
    if (enabledRaw === '0' || enabledRaw.toLowerCase() === 'false') {
      return { ok: true, installed: false, reason: 'disabled_env' };
    }

    if (globalThis[INSTALL_KEY]) {
      return { ok: true, installed: false, reason: 'already_installed' };
    }

    if (!globalThis[PATCHED_CREATE_KEY]) {
      const originalCreateServer = http.createServer.bind(http);
      http.createServer = function patchedCreateServer(...args) {
        const server = originalCreateServer(...args);
        attachListener(server);
        return server;
      };
      globalThis[PATCHED_CREATE_KEY] = true;
    }

    if (!globalThis[PATCHED_EMIT_KEY]) {
      const originalEmit = http.Server.prototype.emit;
      http.Server.prototype.emit = function patchedEmit(event, ...args) {
        try {
          if (event === 'request') {
            const req = args[0];
            if (shouldEmit(req)) {
              emitSignal(req);
            }
          }
        } catch {
          // fail-open
        }
        return originalEmit.call(this, event, ...args);
      };
      globalThis[PATCHED_EMIT_KEY] = true;
    }

    globalThis[INSTALL_KEY] = true;

    try {
      const ports = process.env.OPENCLAW_CONTRACT_INGRESS_PORTS || '18789,18791,18792';
      if (logger && typeof logger.info === 'function') {
        logger.info('contract_ingress_hook_installed', { ports });
      } else {
        console.error('[contract_signal] ingress_hook_installed ports=%s', ports);
      }
    } catch {
      // fail-open
    }

    return { ok: true, installed: true };
  } catch (error) {
    return { ok: false, error: String(error?.message || error) };
  }
}
