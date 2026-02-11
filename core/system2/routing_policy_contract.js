'use strict';

const { BACKENDS } = require('../model_constants');

const POLICY_VERSION = '1.0.0';

function clampNumber(value, min, max, fallback) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return fallback;
  }
  return Math.min(Math.max(numeric, min), max);
}

function toLower(value) {
  return String(value || '').trim().toLowerCase();
}

function isUnavailable(health) {
  const state = toLower(health && health.state);
  return state === 'down' || state === 'unavailable';
}

function evaluateRoutingDecision(input = {}) {
  const requestType = toLower(input.request_type || input.requestType || 'general');
  const privacyLevel = toLower(input.privacy_level || input.privacyLevel || 'external_ok');
  const urgency = toLower(input.urgency || 'interactive');
  const provenance = toLower(input.provenance || 'first_party');
  const toolNeeds = Array.isArray(input.tool_needs || input.toolNeeds)
    ? (input.tool_needs || input.toolNeeds).map((item) => String(item))
    : [];

  const budget = input.budget && typeof input.budget === 'object' ? input.budget : {};
  const systemHealth =
    input.system_health && typeof input.system_health === 'object' ? input.system_health : {};
  const system1Health =
    systemHealth.system1 && typeof systemHealth.system1 === 'object' ? systemHealth.system1 : {};
  const system2Health =
    systemHealth.system2 && typeof systemHealth.system2 === 'object' ? systemHealth.system2 : {};

  const budgetRemaining = clampNumber(
    budget.remaining ?? budget.remaining_tokens,
    0,
    Number.MAX_SAFE_INTEGER,
    8000
  );
  const budgetCap = clampNumber(
    budget.cap ?? budget.token_cap,
    1,
    Number.MAX_SAFE_INTEGER,
    Math.max(8000, budgetRemaining)
  );

  const degradeFlags = {
    tools_disabled: false,
    local_only: false,
    read_only_memory: false,
    deny_reason: null
  };

  let selectedModelRoute = BACKENDS.ANTHROPIC_CLAUDE_API;

  if (privacyLevel === 'local_only') {
    degradeFlags.local_only = true;
    selectedModelRoute = BACKENDS.LOCAL_QWEN;
  }

  if (isUnavailable(system1Health)) {
    degradeFlags.local_only = true;
    selectedModelRoute = BACKENDS.LOCAL_QWEN;
  }

  if (toLower(system2Health.mode) === 'degraded') {
    degradeFlags.tools_disabled = true;
    degradeFlags.read_only_memory = true;
  }

  if (budgetRemaining <= 0) {
    degradeFlags.tools_disabled = true;
    degradeFlags.local_only = true;
    degradeFlags.read_only_memory = true;
    degradeFlags.deny_reason = 'budget_exhausted';
    selectedModelRoute = BACKENDS.LOCAL_QWEN;
  }

  if (requestType === 'coding' || requestType === 'analysis') {
    selectedModelRoute = degradeFlags.local_only ? BACKENDS.LOCAL_QWEN : BACKENDS.LITELLM_PROXY;
  }

  if (requestType === 'planning' || requestType === 'status') {
    selectedModelRoute = BACKENDS.LOCAL_QWEN;
  }

  if (provenance === 'untrusted') {
    degradeFlags.tools_disabled = true;
  }

  const toolAllowlistDecision = degradeFlags.tools_disabled
    ? {
        mode: 'deny',
        allowed_tools: []
      }
    : {
        mode: 'allow_readonly',
        allowed_tools: toolNeeds.filter((toolName) =>
          ['list_dir', 'read_file'].includes(toLower(toolName))
        )
      };

  const maxTokensBase = urgency === 'batch' ? 4096 : 2048;
  const maxTokens = Math.min(maxTokensBase, Math.max(256, budgetRemaining || 256));
  const maxCalls = urgency === 'batch' ? 4 : 2;

  const requiredEvidenceArtifacts = ['routing_decision', 'model_call'];
  if (toolNeeds.length > 0) {
    requiredEvidenceArtifacts.push('tool_call', 'artifact_write');
  }
  if (degradeFlags.local_only || degradeFlags.tools_disabled || degradeFlags.read_only_memory) {
    requiredEvidenceArtifacts.push('degraded_mode_entered');
  }

  return {
    policy_version: POLICY_VERSION,
    inputs: {
      request_type: requestType,
      privacy_level: privacyLevel,
      urgency,
      provenance,
      tool_needs: toolNeeds
    },
    selected_model_route: selectedModelRoute,
    tool_allowlist_decision: toolAllowlistDecision,
    budget_allocation: {
      remaining: budgetRemaining,
      cap: budgetCap,
      max_tokens: maxTokens,
      max_calls: maxCalls
    },
    required_evidence_artifacts: Array.from(new Set(requiredEvidenceArtifacts)),
    degrade_flags: degradeFlags
  };
}

module.exports = {
  POLICY_VERSION,
  evaluateRoutingDecision
};
