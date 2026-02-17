'use strict';

/**
 * Ask-first authorization gate for broad actions.
 *
 * Deny-by-default for untrusted contexts unless explicit approval is present.
 * This module does not mutate process.env and must not log secrets.
 */

const path = require('node:path');
const { decide } = require('./tool_governance');

class ApprovalRequiredError extends Error {
  constructor(message) {
    super(message || 'operator approval required');
    this.name = 'ApprovalRequiredError';
    this.code = 'APPROVAL_REQUIRED';
  }
}

class ToolDeniedError extends Error {
  constructor(message) {
    super(message || 'tool action denied by governance policy');
    this.name = 'ToolDeniedError';
    this.code = 'TOOL_DENIED';
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

function requireApproval(action, ctx, detail = {}) {
  const trustLevel = (ctx && ctx.trustLevel) || 'untrusted';
  const repoRoot = detail.repoRoot || path.resolve(__dirname, '..', '..', '..');

  const policy = decide(
    {
      action,
      targetPath: detail.targetPath
    },
    { trustLevel },
    { repoRoot }
  );

  if (policy.decision === 'allow') {
    return { allowed: true, mechanism: 'governance_allow', policyRef: policy.policyRef };
  }
  if (policy.decision === 'deny') {
    throw new ToolDeniedError(policy.reason);
  }

  // Operator session approval (local-only) is the simplest "yes".
  // The HTTP edge should pass allowOperatorEnv=false to avoid foot-guns.
  if (detail.allowOperatorEnv !== false) {
    if (hasOperatorSessionApproval(detail.env || process.env)) {
      return { allowed: true, mechanism: 'operator_env' };
    }
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
  ToolDeniedError,
  hasOperatorSessionApproval,
  parseApproveTokens,
  requireApproval
};
