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

// Default per-run caps for high-risk action classes (CSA CCM v4 AASC-02, AASC-04).
const DEFAULT_ACTION_CLASS_CAPS = Object.freeze({ D: 5, C: 10 });
// Window for loop detection: last N tool calls examined.
const LOOP_WINDOW = 10;
// Minimum repetitions of the same (tool, args) pair within the window to declare a loop.
const LOOP_MIN_REPEAT = 3;

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

    // Action-class tracking (CSA CCM v4 AASC-02, IVS-01).
    this.actionClassCounts = { A: 0, B: 0, C: 0, D: 0, E: 0 };
    const suppliedCaps = options.actionClassCaps ?? {};
    this.actionClassCaps = {
      ...DEFAULT_ACTION_CLASS_CAPS,
      ...Object.fromEntries(
        Object.entries(suppliedCaps).map(([k, v]) => [k, Number(v)])
      )
    };

    // Loop detection ring buffer (last LOOP_WINDOW tool calls).
    this.recentTools = [];
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
      tripped_reason: this.trippedReason,
      action_class_counts: { ...this.actionClassCounts },
      action_class_caps: { ...this.actionClassCaps }
    };
  }

  /**
   * Record an autonomous agent action for class-cap enforcement and loop detection.
   * Returns { ok, reason } — ok=false if a cap was exceeded or a loop detected.
   *
   * @param {'A'|'B'|'C'|'D'|'E'} actionClass
   * @param {string} toolName
   * @param {string} [argsSummary]
   */
  recordAction(actionClass, toolName, argsSummary = '') {
    if (this.state === STATES.OPEN) {
      return { ok: false, reason: 'budget_exhausted', state: this.state };
    }

    const cls = String(actionClass).toUpperCase();
    if (!Object.hasOwn(this.actionClassCounts, cls)) {
      return { ok: false, reason: `unknown_action_class:${cls}`, state: this.state };
    }

    this.actionClassCounts[cls] += 1;

    // Push to ring buffer and trim to window.
    const fingerprint = `${toolName}::${String(argsSummary).slice(0, 128)}`;
    this.recentTools.push(fingerprint);
    if (this.recentTools.length > LOOP_WINDOW) {
      this.recentTools.shift();
    }

    // Check action-class cap.
    const cap = this.actionClassCaps[cls];
    if (cap !== undefined && this.actionClassCounts[cls] >= cap) {
      return this._trip(`action_class_cap_exceeded:${cls}`);
    }

    // Check loop.
    if (this.isLooping()) {
      return this._trip('autonomous_loop_detected');
    }

    return {
      ok: true,
      state: this.state,
      actionClass: cls,
      classCount: this.actionClassCounts[cls],
      classCap: cap
    };
  }

  /**
   * Returns true if any single (tool+args) fingerprint appears LOOP_MIN_REPEAT
   * or more times in the last LOOP_WINDOW actions.
   */
  isLooping() {
    if (this.recentTools.length < LOOP_MIN_REPEAT) return false;
    const freq = new Map();
    for (const fp of this.recentTools) {
      freq.set(fp, (freq.get(fp) || 0) + 1);
      if (freq.get(fp) >= LOOP_MIN_REPEAT) return true;
    }
    return false;
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

    // Reset action-class tracking.
    this.actionClassCounts = { A: 0, B: 0, C: 0, D: 0, E: 0 };
    this.recentTools = [];

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
  BudgetCircuitBreaker,
  DEFAULT_ACTION_CLASS_CAPS,
  LOOP_WINDOW,
  LOOP_MIN_REPEAT
};
