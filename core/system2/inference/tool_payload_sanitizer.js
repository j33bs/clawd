'use strict';

function strictModeEnabled() {
  const value = String(process.env.OPENCLAW_STRICT_TOOL_PAYLOAD || '').trim().toLowerCase();
  return value === '1' || value === 'true' || value === 'yes';
}

function hasNonEmptyTools(payload) {
  return Boolean(payload && Array.isArray(payload.tools) && payload.tools.length > 0);
}

function createBypassError({ provider_id, model_id, callsite_tag }) {
  const err = new Error('payload sanitizer bypassed');
  err.code = 'TOOL_PAYLOAD_SANITIZER_BYPASSED';
  err.details = {
    provider_id: String(provider_id || ''),
    model_id: String(model_id || ''),
    callsite_tag: String(callsite_tag || ''),
    remediation: 'payload sanitizer bypassed: ensure final dispatch calls enforceToolPayloadInvariant().'
  };
  return err;
}

function sanitizeToolPayload(payload, providerCaps = null) {
  if (!payload || typeof payload !== 'object') return payload;

  const next = { ...payload };
  const supportsTools = !providerCaps || providerCaps.tool_calls_supported !== false;

  if (!supportsTools) {
    delete next.tools;
    delete next.tool_choice;
    return next;
  }

  const tools = next.tools;
  const hasNonEmptyTools = Array.isArray(tools) && tools.length > 0;
  if (!hasNonEmptyTools) {
    delete next.tools;
    delete next.tool_choice;
  }

  return next;
}

function enforceToolPayloadInvariant(payload, providerCaps = null, context = {}) {
  if (!payload || typeof payload !== 'object') return payload;
  const hasToolChoice = Object.prototype.hasOwnProperty.call(payload, 'tool_choice');
  const invalidAutoShape = hasToolChoice && !hasNonEmptyTools(payload);
  if (invalidAutoShape) {
    if (strictModeEnabled()) {
      throw createBypassError(context);
    }
    const warning = {
      level: 'warn',
      event: 'tool_payload_sanitized_after_invalid_shape',
      provider_id: String(context.provider_id || ''),
      model_id: String(context.model_id || ''),
      callsite_tag: String(context.callsite_tag || ''),
      message: 'payload sanitizer bypassed; stripped invalid tool_choice/tools shape'
    };
    console.error('[openclaw.tool_payload]', JSON.stringify(warning));
  }
  return sanitizeToolPayload(payload, providerCaps);
}

module.exports = {
  sanitizeToolPayload,
  enforceToolPayloadInvariant
};
