'use strict';

const { decide } = require('./security/tool_governance');

function isEnabled(env = process.env) {
  return String(env.OPENCLAW_ENABLE_SKILL_COMPOSER || '0') === '1';
}

function composeWorkflow({ goal, toolCalls = [], context = {} }, opts = {}) {
  const env = opts.env || process.env;
  const enabled = isEnabled(env);

  if (!enabled) {
    return {
      enabled: false,
      reason: 'feature_flag_disabled',
      goal: goal || '',
      steps: []
    };
  }

  const repoRoot = opts.repoRoot || process.cwd();
  const steps = toolCalls.map((toolCall, index) => {
    const policy = decide(toolCall, context, { repoRoot });
    return {
      index,
      tool: toolCall.tool || toolCall.action || 'unknown',
      action: toolCall.action || '',
      decision: policy.decision,
      policyRef: policy.policyRef,
      reason: policy.reason,
      executable: policy.decision === 'allow'
    };
  });

  return {
    enabled: true,
    goal: goal || '',
    steps
  };
}

module.exports = {
  composeWorkflow,
  isEnabled
};
