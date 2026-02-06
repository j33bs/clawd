const { ERROR_CODES } = require('./model_constants');

function toIso(date) {
  return date ? date.toISOString() : null;
}

class CooldownManager {
  constructor(options = {}) {
    this.cooldownMinutes = Number(options.cooldownMinutes || process.env.MODEL_ROUTER_COOLDOWN_MINUTES || 30);
    this.timeoutWindowMinutes = Number(
      options.timeoutWindowMinutes || process.env.MODEL_ROUTER_TIMEOUT_WINDOW_MINUTES || 5
    );
    this.timeoutStrikes = Number(options.timeoutStrikes || process.env.MODEL_ROUTER_TIMEOUT_STRIKES || 2);

    this.state = {
      oath: {
        disabledUntil: null,
        lastError: null,
        strikeCount: 0,
        lastErrorAt: null
      },
      anthropic: {
        disabledUntil: null,
        lastError: null,
        strikeCount: 0,
        lastErrorAt: null
      }
    };
  }

  getState(key) {
    return this.state[key] || null;
  }

  isDisabled(key, now = new Date()) {
    const state = this.getState(key);
    if (!state || !state.disabledUntil) {
      return false;
    }
    return new Date(state.disabledUntil).getTime() > now.getTime();
  }

  clearExpired(now = new Date()) {
    const events = [];

    Object.entries(this.state).forEach(([key, value]) => {
      if (!value.disabledUntil) {
        return;
      }

      if (new Date(value.disabledUntil).getTime() <= now.getTime()) {
        value.disabledUntil = null;
        value.strikeCount = 0;
        events.push({
          event_type: 'COOLDOWN_CLEAR',
          backend_key: key,
          trigger_code: ERROR_CODES.NONE,
          timestamp: toIso(now),
          rationale: 'cooldown_expired'
        });
      }
    });

    return events;
  }

  recordError(key, normalizedCode, now = new Date()) {
    const state = this.getState(key);
    if (!state) {
      return { cooldownSet: false, state: null };
    }

    const previousErrorAt = state.lastErrorAt ? new Date(state.lastErrorAt).getTime() : null;
    const previousError = state.lastError;

    state.lastError = normalizedCode;
    state.lastErrorAt = toIso(now);

    let shouldSetCooldown = false;

    if (
      normalizedCode === ERROR_CODES.AUTH ||
      normalizedCode === ERROR_CODES.RATE_LIMIT ||
      normalizedCode === ERROR_CODES.QUOTA ||
      normalizedCode === ERROR_CODES.CONTEXT
    ) {
      shouldSetCooldown = true;
      state.strikeCount = 0;
    } else if (normalizedCode === ERROR_CODES.TIMEOUT) {
      const windowMs = this.timeoutWindowMinutes * 60 * 1000;

      if (
        previousErrorAt &&
        previousError === ERROR_CODES.TIMEOUT &&
        now.getTime() - previousErrorAt <= windowMs
      ) {
        state.strikeCount += 1;
      } else {
        state.strikeCount = 1;
      }

      if (state.strikeCount >= this.timeoutStrikes) {
        shouldSetCooldown = true;
      }
    }

    if (!shouldSetCooldown) {
      return { cooldownSet: false, state: { ...state } };
    }

    const disabledUntil = new Date(now.getTime() + this.cooldownMinutes * 60 * 1000);
    state.disabledUntil = toIso(disabledUntil);

    return {
      cooldownSet: true,
      state: { ...state }
    };
  }
}

module.exports = CooldownManager;
