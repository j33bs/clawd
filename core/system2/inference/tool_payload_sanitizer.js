'use strict';

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

module.exports = {
  sanitizeToolPayload
};
