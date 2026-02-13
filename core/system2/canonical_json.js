'use strict';

/**
 * Deterministic JSON serialization.
 *
 * This is intentionally minimal and side-effect free:
 * - Objects are serialized with lexicographically sorted keys (recursive).
 * - Arrays preserve order.
 * - No whitespace variance.
 *
 * Note: This is not a general-purpose serializer (e.g., does not support cycles).
 */

function stableStringify(value) {
  if (value === null) return 'null';
  if (typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) {
    return '[' + value.map((v) => stableStringify(v)).join(',') + ']';
  }
  const keys = Object.keys(value).sort();
  return '{' + keys.map((k) => JSON.stringify(k) + ':' + stableStringify(value[k])).join(',') + '}';
}

module.exports = {
  stableStringify
};

