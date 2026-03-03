'use strict';

const crypto = require('node:crypto');

const SAFE_DEBUG_SUMMARY = new Set([
  'timeout',
  'rate_limit',
  'provider_unavailable',
  'network_error',
  'validation_error',
  'internal_error'
]);

function nextRequestId(prefix = 'req') {
  const head = String(prefix || 'req').replace(/[^a-z0-9_-]/gi, '').toLowerCase() || 'req';
  return `${head}-${Date.now().toString(36)}-${crypto.randomBytes(3).toString('hex')}`;
}

function _redactString(text) {
  let out = String(text ?? '');
  out = out.replace(/(authorization\s*:\s*bearer\s+)[^\s,;]+/gi, '$1<redacted>');
  out = out.replace(/\bBearer\s+[A-Za-z0-9._~+\-/=]{8,}/g, 'Bearer <redacted>');
  out = out.replace(/\b(sk|gsk|xoxb|xoxp)-[A-Za-z0-9_-]{8,}\b/gi, '<redacted-token>');
  out = out.replace(/((?:api[_-]?key|token|secret|password)\s*[:=]\s*)([^\s,;]+)/gi, '$1<redacted>');
  out = out.replace(/(cookie\s*:\s*)([^\r\n]+)/gi, '$1<redacted>');
  out = out.replace(/(set-cookie\s*:\s*)([^\r\n]+)/gi, '$1<redacted>');
  return out;
}

function redact(value) {
  if (typeof value === 'string') return _redactString(value);
  if (value === null || value === undefined) return value;
  if (Array.isArray(value)) return value.map((item) => redact(item));
  if (typeof value === 'object') {
    const out = {};
    for (const [k, v] of Object.entries(value)) {
      if (/authorization|cookie|token|secret|password|api[_-]?key/i.test(k)) {
        out[k] = '<redacted>';
      } else {
        out[k] = redact(v);
      }
    }
    return out;
  }
  return value;
}

function createSafeErrorEnvelope({
  publicMessage = 'Request failed. Please retry shortly.',
  errorCode = 'gateway_error',
  requestId,
  occurredAt,
  logRef,
  debugSummary
} = {}) {
  const normalizedDebug = String(debugSummary || '').trim().toLowerCase();
  return {
    public_message: _redactString(publicMessage),
    error_code: String(errorCode),
    request_id: requestId ? String(requestId) : nextRequestId('err'),
    occurred_at: occurredAt || new Date().toISOString(),
    log_ref: logRef || 'check local gateway logs with request_id',
    debug_summary: SAFE_DEBUG_SUMMARY.has(normalizedDebug) ? normalizedDebug : undefined
  };
}

function adapterPublicErrorFields(envelope) {
  return {
    public_message: String(envelope.public_message || ''),
    error_code: String(envelope.error_code || 'gateway_error'),
    request_id: String(envelope.request_id || nextRequestId('err'))
  };
}

function formatAdapterPublicError(envelope) {
  const safe = adapterPublicErrorFields(envelope);
  return `${safe.public_message}\nerror_code: ${safe.error_code}\nrequest_id: ${safe.request_id}`;
}

function createRedactedGatewayLogger(emitFn) {
  const emit = typeof emitFn === 'function' ? emitFn : () => {};
  return {
    log(event, detail) {
      emit({ ts: new Date().toISOString(), event: String(event || 'event'), detail: redact(detail) });
    },
    error(event, detail) {
      emit({ ts: new Date().toISOString(), level: 'error', event: String(event || 'error'), detail: redact(detail) });
    }
  };
}

module.exports = {
  SAFE_DEBUG_SUMMARY,
  nextRequestId,
  redact,
  createSafeErrorEnvelope,
  adapterPublicErrorFields,
  formatAdapterPublicError,
  createRedactedGatewayLogger
};
