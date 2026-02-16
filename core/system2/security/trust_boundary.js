'use strict';

/**
 * Trust boundary classification for System-2.
 *
 * Policy (fail-closed):
 * - Anything arriving via the HTTP edge is UNTRUSTED by default.
 * - Trusted contexts must be explicitly marked by the operator/runtime.
 */

function classifyRequest(ctx = {}) {
  const source = String(ctx.source || 'unknown');
  const identity = ctx.identity ? String(ctx.identity) : undefined;

  if (source === 'http_edge') {
    return { trustLevel: 'untrusted', identity };
  }

  if (ctx.operator === true) {
    return { trustLevel: 'trusted', identity };
  }

  return { trustLevel: 'untrusted', identity };
}

function isUntrusted(ctx = {}) {
  const res = classifyRequest(ctx);
  return res.trustLevel !== 'trusted';
}

module.exports = {
  classifyRequest,
  isUntrusted
};

