'use strict';

/**
 * Budget circuit breaker for System-2 gateway.
 *
 * Tracks token and call budgets per run, enforces caps,
 * and trips when budgets are exhausted. Emits structured
 * events on trip and reset.
 */

const STATES = Object.freeze({
  CLOSED: 'closed',
  OPEN: 'open'
});

class BudgetCircuitBreaker {
  constructor(options = {}) {
    this.tokenCap = Number(options.tokenCap ?? 100000);
    this.callCap = Number(options.callCap ?? 200);
    this.tokensUsed = 0;
    this.callsMade = 0;
    this.state = STATES.CLOSED;
    this.trippedAt = null;
    this.trippedReason = null;
    this.onEvent = typeof options.onEvent === 'function' ? options.onEvent : null;
  }

  _emitEvent(event) {
    if (this.onEvent) {
      this.onEvent({
        ts: new Date().toISOString(),
        ...event
      });
    }
  }

  /**
   * Record token usage from a model call.
   * Returns { ok, remaining, state } or trips the breaker.
   */
  recordUsage({ inputTokens = 0, outputTokens = 0 } = {}) {
    if (this.state === STATES.OPEN) {
      return {
        ok: false,
        reason: 'budget_exhausted',
        state: this.state,
        tokensUsed: this.tokensUsed,
        tokenCap: this.tokenCap
      };
    }

    const tokens = (Number(inputTokens) || 0) + (Number(outputTokens) || 0);
    this.tokensUsed += tokens;
    this.callsMade += 1;

    if (this.tokensUsed >= this.tokenCap) {
      return this._trip('token_cap_exceeded');
    }

    if (this.callsMade >= this.callCap) {
      return this._trip('call_cap_exceeded');
    }

    return {
      ok: true,
      state: this.state,
      tokensUsed: this.tokensUsed,
      tokenCap: this.tokenCap,
      remaining: this.tokenCap - this.tokensUsed,
      callsMade: this.callsMade,
      callCap: this.callCap
    };
  }

  /**
   * Check whether a request with the given token estimate can proceed.
   */
  canProceed(estimatedTokens = 0) {
    if (this.state === STATES.OPEN) {
      return false;
    }
    return (this.tokensUsed + (Number(estimatedTokens) || 0)) < this.tokenCap;
  }

  /**
   * Get current budget allocation for routing decisions.
   */
  getAllocation() {
    return {
      remaining: Math.max(0, this.tokenCap - this.tokensUsed),
      cap: this.tokenCap,
      tokens_used: this.tokensUsed,
      calls_made: this.callsMade,
      call_cap: this.callCap,
      state: this.state,
      tripped_at: this.trippedAt,
      tripped_reason: this.trippedReason
    };
  }

  _trip(reason) {
    this.state = STATES.OPEN;
    this.trippedAt = new Date().toISOString();
    this.trippedReason = reason;

    this._emitEvent({
      event_type: 'budget_exhausted',
      reason,
      tokens_used: this.tokensUsed,
      token_cap: this.tokenCap,
      calls_made: this.callsMade,
      call_cap: this.callCap
    });

    return {
      ok: false,
      reason,
      state: this.state,
      tokensUsed: this.tokensUsed,
      tokenCap: this.tokenCap,
      callsMade: this.callsMade,
      callCap: this.callCap
    };
  }

  /**
   * Reset the breaker (for new budget windows or operator override).
   */
  reset(options = {}) {
    const previousState = this.state;
    this.tokensUsed = 0;
    this.callsMade = 0;
    this.state = STATES.CLOSED;
    this.trippedAt = null;
    this.trippedReason = null;

    if (Number(options.tokenCap) > 0) {
      this.tokenCap = Number(options.tokenCap);
    }
    if (Number(options.callCap) > 0) {
      this.callCap = Number(options.callCap);
    }

    if (previousState === STATES.OPEN) {
      this._emitEvent({
        event_type: 'budget_reset',
        previous_state: previousState,
        new_token_cap: this.tokenCap,
        new_call_cap: this.callCap
      });
    }

    return this.getAllocation();
  }
}

module.exports = {
  STATES,
  BudgetCircuitBreaker
};
