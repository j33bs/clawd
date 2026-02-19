'use strict';

const TOOL_JSON_PATTERN = /"tool"\s*:\s*"(?:exec|browser|message|cron|process|shell|write_file|read_file)"/gi;
const TOOL_BLOCK_PATTERN = /<\s*tool[^>]*>[\s\S]*?<\s*\/\s*tool\s*>/gi;
const METADATA_BLOCK_PATTERN = /<\s*metadata[^>]*>[\s\S]*?<\s*\/\s*metadata\s*>/gi;
const ROLE_PREFIX_PATTERN = /^\s*(system|assistant|developer|tool)\s*:\s*/gim;

function _replaceAll(input, pattern, replacement, type, report) {
  let count = 0;
  const output = input.replace(pattern, () => {
    count += 1;
    return replacement;
  });
  if (count > 0) {
    report.push({ type, count });
  }
  return output;
}

function sanitizeContextInput(input) {
  const text = typeof input === 'string' ? input : String(input || '');
  const report = [];

  let sanitized = text;
  sanitized = _replaceAll(sanitized, TOOL_BLOCK_PATTERN, '[redacted_tool_block]', 'tool_block', report);
  sanitized = _replaceAll(sanitized, METADATA_BLOCK_PATTERN, '[redacted_metadata_block]', 'metadata_block', report);
  sanitized = _replaceAll(sanitized, TOOL_JSON_PATTERN, '"tool":"[redacted]"', 'tool_json', report);
  sanitized = _replaceAll(sanitized, ROLE_PREFIX_PATTERN, '', 'role_prefix', report);

  return {
    originalText: text,
    sanitizedText: sanitized,
    redactions: report
  };
}

module.exports = {
  sanitizeContextInput
};
