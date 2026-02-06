const { ERROR_CODES } = require('./model_constants');

function textIncludes(text, patterns) {
  const normalized = String(text || '').toLowerCase();
  return patterns.some((pattern) => normalized.includes(pattern));
}

function getStatus(error) {
  if (!error || typeof error !== 'object') {
    return null;
  }
  if (typeof error.status === 'number') {
    return error.status;
  }
  if (typeof error.statusCode === 'number') {
    return error.statusCode;
  }
  if (error.response && typeof error.response.status === 'number') {
    return error.response.status;
  }
  return null;
}

function getRawCode(error) {
  if (!error || typeof error !== 'object') {
    return null;
  }
  return error.code || error.type || (error.error && error.error.type) || null;
}

function normalizeProviderError(error, provider = 'UNKNOWN') {
  const status = getStatus(error);
  const rawCode = getRawCode(error);
  const message = String(
    (error && (error.message || error.error || error.body || error.details)) ||
      error ||
      'Unknown provider error'
  );
  const combined = `${rawCode || ''} ${message}`.trim();

  let code = ERROR_CODES.UNKNOWN;

  if (
    status === 401 ||
    status === 403 ||
    textIncludes(combined, ['authentication_error', 'invalid bearer token', 'unauthorized', 'forbidden'])
  ) {
    code = ERROR_CODES.AUTH;
  } else if (
    textIncludes(combined, ['quota_exceeded', 'insufficient_quota', 'billing_limit', 'credit exhausted'])
  ) {
    code = ERROR_CODES.QUOTA;
  } else if (
    status === 429 ||
    textIncludes(combined, ['rate_limit', 'too many requests'])
  ) {
    code = ERROR_CODES.RATE_LIMIT;
  } else if (
    textIncludes(combined, ['context_length_exceeded', 'maximum context', 'prompt is too long'])
  ) {
    code = ERROR_CODES.CONTEXT;
  } else if (
    (error && error.name === 'AbortError') ||
    status === 408 ||
    textIncludes(combined, ['timeout', 'timed out', 'etimedout'])
  ) {
    code = ERROR_CODES.TIMEOUT;
  } else if (
    textIncludes(combined, [
      'network',
      'fetch failed',
      'econnrefused',
      'enotfound',
      'socket hang up',
      'tls'
    ])
  ) {
    code = ERROR_CODES.NETWORK;
  }

  return {
    code,
    provider,
    status,
    rawCode: rawCode || null,
    message
  };
}

module.exports = {
  normalizeProviderError
};
