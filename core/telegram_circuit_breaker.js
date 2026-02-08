const DEFAULT_FAILURE_WINDOW_MS = 2 * 60 * 1000;
const DEFAULT_CHAT_ACTION_THRESHOLD = 3;
const DEFAULT_CHAT_ACTION_COOLDOWN_MS = 15 * 60 * 1000;
const DEFAULT_SEND_MESSAGE_THRESHOLD = 5;
const DEFAULT_SEND_MESSAGE_COOLDOWN_MS = 2 * 60 * 1000;

function nowMs(clock) {
  return typeof clock === 'function' ? clock() : Date.now();
}

function logWith(logger, level, message) {
  if (!logger) {
    return;
  }
  if (typeof logger[level] === 'function') {
    logger[level](message);
    return;
  }
  if (typeof logger.log === 'function') {
    logger.log(message);
  }
}

class TelegramCircuitBreaker {
  constructor(options = {}) {
    this.clock = options.clock || null;
    this.logger = options.logger || null;
    this.failureWindowMs = Number(options.failureWindowMs ?? DEFAULT_FAILURE_WINDOW_MS);
    this.methodConfig = {
      sendChatAction: {
        threshold: Number(options.chatActionThreshold ?? DEFAULT_CHAT_ACTION_THRESHOLD),
        cooldownMs: Number(options.chatActionCooldownMs ?? DEFAULT_CHAT_ACTION_COOLDOWN_MS)
      },
      sendMessage: {
        threshold: Number(options.sendMessageThreshold ?? DEFAULT_SEND_MESSAGE_THRESHOLD),
        cooldownMs: Number(options.sendMessageCooldownMs ?? DEFAULT_SEND_MESSAGE_COOLDOWN_MS)
      }
    };
    this.states = new Map();
  }

  getState(method) {
    if (!this.states.has(method)) {
      this.states.set(method, {
        failures: [],
        openUntil: 0,
        isOpen: false
      });
    }
    return this.states.get(method);
  }

  isOpen(method) {
    const state = this.getState(method);
    const now = nowMs(this.clock);

    if (state.isOpen && now >= state.openUntil) {
      state.isOpen = false;
      state.openUntil = 0;
      state.failures = [];
      logWith(this.logger, 'info', `telegram breaker closed for ${method}`);
    }

    return state.isOpen;
  }

  recordFailure(method) {
    const config = this.methodConfig[method] || {
      threshold: DEFAULT_CHAT_ACTION_THRESHOLD,
      cooldownMs: DEFAULT_CHAT_ACTION_COOLDOWN_MS
    };
    const state = this.getState(method);
    const now = nowMs(this.clock);

    state.failures = state.failures.filter((timestamp) => now - timestamp <= this.failureWindowMs);
    state.failures.push(now);

    if (!state.isOpen && state.failures.length >= config.threshold) {
      state.isOpen = true;
      state.openUntil = now + config.cooldownMs;
      logWith(this.logger, 'warn', `telegram breaker opened for ${method}`);
    }
  }

  recordSuccess(method) {
    const state = this.getState(method);
    if (state.isOpen) {
      return;
    }
    state.failures = [];
  }
}

module.exports = TelegramCircuitBreaker;
