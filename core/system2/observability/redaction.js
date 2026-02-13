'use strict';

const { redactIfSensitive } = require('../inference/config');

function deepRedact(value, keyName, options = {}) {
  const redact = options.redactFn || redactIfSensitive;

  if (value === null) return null;
  if (typeof value === 'string') {
    if (typeof keyName === 'string' && keyName.length > 0) {
      return redact(keyName, value);
    }
    return value;
  }
  if (typeof value !== 'object') return value;
  if (Array.isArray(value)) return value.map((v) => deepRedact(v, keyName, options));

  const out = {};
  for (const k of Object.keys(value)) {
    out[k] = deepRedact(value[k], k, options);
  }
  return out;
}

module.exports = {
  deepRedact
};

