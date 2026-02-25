import { logger as rootLogger } from './log.mjs';

function sleep(ms) {
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, ms);
    if (typeof timer.unref === 'function') timer.unref();
  });
}

function parseRetryAfter(value) {
  if (value == null) return null;

  const asNumber = Number(value);
  if (Number.isFinite(asNumber) && asNumber >= 0) {
    return asNumber * 1000;
  }

  const asDate = Date.parse(String(value));
  if (!Number.isFinite(asDate)) return null;

  const delta = asDate - Date.now();
  return delta > 0 ? delta : null;
}

function extractStatus(error) {
  if (!error || typeof error !== 'object') return null;
  if (Number.isFinite(error.status)) return Number(error.status);
  if (Number.isFinite(error.statusCode)) return Number(error.statusCode);
  if (Number.isFinite(error?.response?.status)) return Number(error.response.status);
  return null;
}

function extractRetryAfterMs(error) {
  if (!error || typeof error !== 'object') return null;
  const candidates = [
    error?.retryAfter,
    error?.retry_after,
    error?.response?.headers?.['retry-after'],
    error?.headers?.['retry-after']
  ];

  for (const candidate of candidates) {
    const parsed = parseRetryAfter(candidate);
    if (parsed != null) return parsed;
  }

  return null;
}

function isRetryableError(error) {
  const status = extractStatus(error);
  if (status == null) return false;
  return status === 429 || (status >= 500 && status <= 599);
}

function computeDelayMs(attempt, options, retryAfterMs) {
  if (retryAfterMs != null) {
    return Math.min(options.maxDelayMs, Math.max(0, retryAfterMs));
  }

  const backoff = Math.min(options.maxDelayMs, options.baseDelayMs * (2 ** (attempt - 1)));
  const jitter = Math.floor(options.rand() * options.jitterMs);
  return backoff + jitter;
}

async function retryWithBackoff(task, options = {}) {
  if (typeof task !== 'function') {
    throw new Error('retryWithBackoff requires a function');
  }

  const opts = {
    maxAttempts: options.maxAttempts ?? 3,
    baseDelayMs: options.baseDelayMs ?? 250,
    maxDelayMs: options.maxDelayMs ?? 5_000,
    jitterMs: options.jitterMs ?? 100,
    shouldRetry: options.shouldRetry ?? isRetryableError,
    retryAfterMs: options.retryAfterMs ?? extractRetryAfterMs,
    sleep: options.sleep ?? sleep,
    rand: options.rand ?? Math.random,
    onRetry: options.onRetry,
    logger: options.logger || rootLogger.child({ module: 'retry-backoff' })
  };

  let lastError;
  for (let attempt = 1; attempt <= opts.maxAttempts; attempt += 1) {
    try {
      return await task({ attempt });
    } catch (error) {
      lastError = error;
      if (attempt >= opts.maxAttempts || !opts.shouldRetry(error)) {
        throw error;
      }

      const retryAfterMs = opts.retryAfterMs(error);
      const delayMs = computeDelayMs(attempt, opts, retryAfterMs);
      opts.onRetry?.({ attempt, delayMs, error });
      opts.logger.warn('retrying_request', {
        attempt,
        delayMs,
        status: extractStatus(error)
      });
      await opts.sleep(delayMs);
    }
  }

  throw lastError;
}

export { computeDelayMs, extractRetryAfterMs, extractStatus, isRetryableError, parseRetryAfter, retryWithBackoff };
