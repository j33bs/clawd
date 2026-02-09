'use strict';

const SENSITIVE_KEY_RE = /(token|secret|password|api[_-]?key|authorization|cookie|session|prompt|message|content)/i;
const SENSITIVE_VALUE_RE = /(sk-[a-z0-9_-]{10,}|bearer\s+[a-z0-9._-]{8,}|api[_-]?key\s*[:=])/i;

function isSensitiveKey(key) {
  return SENSITIVE_KEY_RE.test(String(key || ''));
}

function redactString(value) {
  if (SENSITIVE_VALUE_RE.test(value)) {
    return '[REDACTED]';
  }
  return value;
}

function redactValue(value, keyHint = '') {
  if (isSensitiveKey(keyHint)) {
    return '[REDACTED]';
  }

  if (Array.isArray(value)) {
    return value.map((item) => redactValue(item));
  }

  if (value && typeof value === 'object') {
    const out = {};
    for (const [key, child] of Object.entries(value)) {
      out[key] = redactValue(child, key);
    }
    return out;
  }

  if (typeof value === 'string') {
    return redactString(value);
  }

  return value;
}

module.exports = {
  isSensitiveKey,
  redactValue
};
