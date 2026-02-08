// NOTE: This client must be used by Telegram integrations to get breaker/backoff protection.
// TODO: Wire any live Telegram integration through this module.
const TelegramCircuitBreaker = require('./telegram_circuit_breaker');

const DEFAULT_BASE_URL = 'https://api.telegram.org';
const DEFAULT_TIMEOUT_MS = 15000;
const DEFAULT_BASE_DELAY_MS = 500;
const DEFAULT_JITTER_MS = 250;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function randomJitter(rng, maxJitterMs) {
  const value = typeof rng === 'function' ? rng() : Math.random();
  return Math.floor(value * maxJitterMs);
}

function computeBackoff(attempt, baseDelayMs, jitterMs, rng) {
  const base = baseDelayMs * Math.pow(2, attempt);
  return base + randomJitter(rng, jitterMs);
}

function isRetryableStatus(status) {
  if (!status) {
    return false;
  }
  if (status === 429) {
    return true;
  }
  return status >= 500 && status <= 599;
}

function isRetryableError(error) {
  if (!error) {
    return false;
  }
  if (error.name === 'AbortError') {
    return true;
  }
  const message = String(error.message || '').toLowerCase();
  return (
    message.includes('fetch failed') ||
    message.includes('econnreset') ||
    message.includes('etimedout') ||
    message.includes('timeout') ||
    message.includes('socket hang up') ||
    message.includes('network')
  );
}

class TelegramClient {
  constructor(options = {}) {
    this.token = options.token || process.env.TELEGRAM_BOT_TOKEN || null;
    this.baseUrl = (options.baseUrl || DEFAULT_BASE_URL).replace(/\/$/, '');
    this.timeoutMs = Number(options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
    this.baseDelayMs = Number(options.baseDelayMs ?? DEFAULT_BASE_DELAY_MS);
    this.jitterMs = Number(options.jitterMs ?? DEFAULT_JITTER_MS);
    this.maxRetries = {
      sendChatAction: Number(options.maxRetriesChatAction ?? 2),
      sendMessage: Number(options.maxRetriesSendMessage ?? 4)
    };
    this.fetchFn = options.fetchFn || fetch;
    this.sleepFn = options.sleepFn || sleep;
    this.rng = options.rng || Math.random;
    this.breaker = options.breaker || new TelegramCircuitBreaker({ logger: options.logger });
    this.logger = options.logger || null;
  }

  async sendChatAction(payload) {
    return this.request('sendChatAction', payload, { allowBreakerSkip: true });
  }

  async sendMessage(payload) {
    return this.request('sendMessage', payload, { allowBreakerSkip: false });
  }

  async request(method, payload, options = {}) {
    if (!this.token) {
      return { ok: false, error: new Error('TELEGRAM_BOT_TOKEN is missing') };
    }

    const allowBreakerSkip = options.allowBreakerSkip === true;
    if (allowBreakerSkip && this.breaker.isOpen(method)) {
      return { ok: true, skipped: true, reason: 'circuit_open' };
    }

    const maxRetries = this.maxRetries[method] ?? 0;
    let attempt = 0;

    while (attempt <= maxRetries) {
      const result = await this.tryOnce(method, payload);

      if (result.ok) {
        this.breaker.recordSuccess(method);
        return result;
      }

      this.breaker.recordFailure(method);

      const retryAfterMs = result.retryAfterMs || null;
      const retryable = result.retryable === true;

      if (!retryable || attempt >= maxRetries) {
        return result;
      }

      const delay = retryAfterMs || computeBackoff(attempt, this.baseDelayMs, this.jitterMs, this.rng);
      await this.sleepFn(delay);
      attempt += 1;
    }

    return { ok: false, error: new Error('Telegram request failed') };
  }

  async tryOnce(method, payload) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    const url = `${this.baseUrl}/bot${this.token}/${method}`;

    try {
      const response = await this.fetchFn(url, {
        method: 'POST',
        headers: {
          'content-type': 'application/json'
        },
        body: JSON.stringify(payload || {}),
        signal: controller.signal
      });

      clearTimeout(timer);

      const json = await response.json().catch(() => null);
      const status = response.status;

      if (!response.ok) {
        return {
          ok: false,
          status,
          retryable: isRetryableStatus(status),
          retryAfterMs: this.extractRetryAfterMs(json),
          error: new Error(`Telegram request failed: ${status}`),
          payload: json
        };
      }

      if (json && json.ok === false) {
        const errorCode = json.error_code || status;
        return {
          ok: false,
          status: errorCode,
          retryable: isRetryableStatus(errorCode),
          retryAfterMs: this.extractRetryAfterMs(json),
          error: new Error(json.description || 'Telegram error'),
          payload: json
        };
      }

      return { ok: true, status, payload: json };
    } catch (error) {
      clearTimeout(timer);
      return {
        ok: false,
        status: null,
        retryable: isRetryableError(error),
        retryAfterMs: null,
        error
      };
    }
  }

  extractRetryAfterMs(payload) {
    if (!payload || !payload.parameters || !payload.parameters.retry_after) {
      return null;
    }
    const retryAfterSeconds = Number(payload.parameters.retry_after);
    if (Number.isNaN(retryAfterSeconds)) {
      return null;
    }
    return retryAfterSeconds * 1000;
  }
}

module.exports = TelegramClient;
