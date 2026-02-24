'use strict';

const SCHEMA_ID = 'openclaw.event_envelope.v1';
const FORBIDDEN_KEYS = new Set([
  'prompt',
  'text',
  'body',
  'document_body',
  'documentbody',
  'messages',
  'content',
  'raw_content',
  'raw'
]);

function utcNowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
}

function sanitize(value) {
  if (Array.isArray(value)) return value.map((item) => sanitize(item));
  if (value && typeof value === 'object') {
    const out = {};
    for (const [key, item] of Object.entries(value)) {
      if (FORBIDDEN_KEYS.has(String(key).trim().toLowerCase())) continue;
      out[String(key)] = sanitize(item);
    }
    return out;
  }
  return value;
}

function makeEnvelope({ event, severity, component, corr_id, details, ts }) {
  return {
    schema: SCHEMA_ID,
    ts: String(ts || utcNowIso()),
    event: String(event || ''),
    severity: String(severity || 'INFO').toUpperCase(),
    component: String(component || ''),
    corr_id: String(corr_id || ''),
    details: sanitize(details || {})
  };
}

function containsForbiddenKeys(value) {
  if (Array.isArray(value)) return value.some((item) => containsForbiddenKeys(item));
  if (value && typeof value === 'object') {
    for (const [key, item] of Object.entries(value)) {
      if (FORBIDDEN_KEYS.has(String(key).trim().toLowerCase())) return true;
      if (containsForbiddenKeys(item)) return true;
    }
  }
  return false;
}

module.exports = {
  SCHEMA_ID,
  makeEnvelope,
  containsForbiddenKeys
};
