'use strict';

/**
 * Ask-first authorization gate for broad actions.
 *
 * Deny-by-default for untrusted contexts unless explicit approval is present.
 * This module does not mutate process.env and must not log secrets.
 */

class ApprovalRequiredError extends Error {
  constructor(message) {
    super(message || 'operator approval required');
    this.name = 'ApprovalRequiredError';
    this.code = 'APPROVAL_REQUIRED';
  }
}

function hasOperatorSessionApproval(env = process.env) {
  return String(env.OPENCLAW_OPERATOR_APPROVED || '') === '1';
}

function parseApproveTokens(env = process.env) {
  // Format: "label:token,label2:token2" OR "tokenA,tokenB"
  const raw = String(env.OPENCLAW_EDGE_APPROVE_TOKENS || '').trim();
  if (!raw) return new Set();
  const out = new Set();
  for (const part of raw.split(',')) {
    const tok = part.trim();
    if (!tok) continue;
    const idx = tok.indexOf(':');
    out.add(idx >= 0 ? tok.slice(idx + 1) : tok);
  }
  return out;
}

function isBroadAction(action) {
  const a = String(action || '').toLowerCase();
  if (!a) return true;
  return (
    a.includes('outbound_http') ||
    a.includes('fs_write_outside_repo') ||
    a.includes('service_control') ||
    a.includes('write_memory') ||
    a.includes('write_governance') ||
    a.includes('spawn_child_process') ||
    a.includes('gateway_rpc_broad')
  );
}

function requireApproval(action, ctx, detail = {}) {
  const trustLevel = (ctx && ctx.trustLevel) || 'untrusted';

  // Trusted contexts are allowed without additional approvals.
  if (trustLevel === 'trusted') {
    return { allowed: true, mechanism: 'trusted' };
  }

  // For untrusted contexts, only broad actions require ask-first.
  if (!isBroadAction(action)) {
    return { allowed: true, mechanism: 'untrusted_non_broad' };
  }

  // Operator session approval (local-only) is the simplest "yes".
  if (hasOperatorSessionApproval(detail.env || process.env)) {
    return { allowed: true, mechanism: 'operator_env' };
  }

  // Per-request approval token (edge).
  if (detail && detail.approveToken) {
    const allowed = parseApproveTokens(detail.env || process.env);
    if (allowed.has(String(detail.approveToken))) {
      return { allowed: true, mechanism: 'approve_header' };
    }
  }

  throw new ApprovalRequiredError();
}

module.exports = {
  ApprovalRequiredError,
  hasOperatorSessionApproval,
  parseApproveTokens,
  requireApproval
};

