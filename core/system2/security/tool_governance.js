'use strict';

const path = require('node:path');

const ALLOWLIST = Object.freeze([
  'read_status',
  'preflight'
]);

const DENY_PATTERNS = Object.freeze([
  'policy_bypass',
  'disable_guard',
  'exfiltrate'
]);

function normalizeAction(action) {
  const a = String(action || '').toLowerCase();
  if (!a) return 'unknown';
  if (a.includes('spawn_child_process') || a.includes('exec') || a.includes('shell')) return 'exec';
  if (a.includes('outbound_http') || a.includes('network') || a.includes('browser') || a.includes('gateway_rpc')) return 'network';
  if (a.includes('fs_write_outside_repo') || a.includes('write_outside_workspace')) return 'fs_write_outside_workspace';
  return a;
}

function isPathOutsideWorkspace(targetPath, repoRoot) {
  if (!targetPath || !repoRoot) return true;
  const workspaceRoot = path.resolve(repoRoot, 'workspace');
  const resolvedTarget = path.resolve(targetPath);
  return !resolvedTarget.startsWith(workspaceRoot + path.sep) && resolvedTarget !== workspaceRoot;
}

function decide(toolCall = {}, context = {}, options = {}) {
  const actionRaw = toolCall.action || toolCall.type || '';
  const action = normalizeAction(actionRaw);
  const trustLevel = String((context && context.trustLevel) || 'untrusted');

  for (const pattern of DENY_PATTERNS) {
    if (action.includes(pattern)) {
      return {
        decision: 'deny',
        reason: `action_denied_${pattern}`,
        policyRef: 'tool_governance.denylist'
      };
    }
  }

  if (ALLOWLIST.includes(action)) {
    return {
      decision: 'allow',
      reason: trustLevel === 'trusted' ? 'trusted_allowlist' : 'allowlist',
      policyRef: 'tool_governance.allowlist'
    };
  }

  if (action === 'exec') {
    return {
      decision: 'ask',
      reason: 'exec_requires_approval',
      policyRef: 'tool_governance.ask_first.exec'
    };
  }

  if (action === 'network') {
    return {
      decision: 'ask',
      reason: 'network_requires_approval',
      policyRef: 'tool_governance.ask_first.network'
    };
  }

  if (action === 'fs_write_outside_workspace') {
    const outside = isPathOutsideWorkspace(toolCall.targetPath, options.repoRoot);
    return {
      decision: outside ? 'ask' : 'allow',
      reason: outside ? 'outside_workspace_write_requires_approval' : 'workspace_write_allowed',
      policyRef: outside
        ? 'tool_governance.ask_first.fs_write_outside_workspace'
        : 'tool_governance.allow.workspace_write'
    };
  }

  return {
    decision: trustLevel === 'trusted' ? 'allow' : 'ask',
    reason: trustLevel === 'trusted' ? 'trusted_default_allow' : 'untrusted_default_ask',
    policyRef: 'tool_governance.default'
  };
}

module.exports = {
  decide,
  normalizeAction,
  isPathOutsideWorkspace
};
