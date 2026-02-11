'use strict';

/**
 * Degraded mode controller for System-2.
 *
 * Manages operational modes (normal, burst, degraded, recovery)
 * as defined in the System-2 design brief. Evaluates system health
 * signals and transitions between modes with structured event emission.
 */

const MODES = Object.freeze({
  NORMAL: 'normal',
  BURST: 'burst',
  DEGRADED: 'degraded',
  RECOVERY: 'recovery'
});

class DegradedModeController {
  constructor(options = {}) {
    this.mode = MODES.NORMAL;
    this.enteredAt = new Date().toISOString();
    this.reason = null;
    this.history = [];
    this.maxHistory = Number(options.maxHistory ?? 50);
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

  _pushHistory(from, to, reason) {
    this.history.push({
      from,
      to,
      reason,
      ts: new Date().toISOString()
    });
    if (this.history.length > this.maxHistory) {
      this.history = this.history.slice(-this.maxHistory);
    }
  }

  /**
   * Transition to a new mode. Returns the new state.
   */
  transitionTo(newMode, reason = null) {
    const validModes = Object.values(MODES);
    if (!validModes.includes(newMode)) {
      throw new Error(`Invalid mode: ${newMode}. Valid: ${validModes.join(', ')}`);
    }

    const previousMode = this.mode;
    if (previousMode === newMode) {
      return this.getState();
    }

    this.mode = newMode;
    this.enteredAt = new Date().toISOString();
    this.reason = reason;
    this._pushHistory(previousMode, newMode, reason);

    this._emitEvent({
      event_type: 'degraded_mode_entered',
      previous_mode: previousMode,
      new_mode: newMode,
      reason
    });

    return this.getState();
  }

  /**
   * Evaluate system health and automatically transition modes.
   *
   * Input shape: {
   *   system1: { state: 'up'|'down'|'saturated' },
   *   system2: { budget_ok, tool_plane_ok, inference_ok },
   *   budget_exhausted: boolean
   * }
   */
  evaluate(health = {}) {
    const s1 = health.system1 || {};
    const s2 = health.system2 || {};
    const s1State = String(s1.state || 'up').toLowerCase();
    const budgetExhausted = Boolean(health.budget_exhausted);

    // Recovery: System-1 is down
    if (s1State === 'down' || s1State === 'unavailable') {
      if (this.mode !== MODES.RECOVERY) {
        this.transitionTo(MODES.RECOVERY, 'system1_unavailable');
      }
      return this.getState();
    }

    // Degraded: budget exhausted or local inference broken
    if (budgetExhausted) {
      if (this.mode !== MODES.DEGRADED) {
        this.transitionTo(MODES.DEGRADED, 'budget_exhausted');
      }
      return this.getState();
    }

    if (s2.inference_ok === false) {
      if (this.mode !== MODES.DEGRADED) {
        this.transitionTo(MODES.DEGRADED, 'local_inference_unavailable');
      }
      return this.getState();
    }

    // Burst: System-1 is saturated, System-2 takes more load
    if (s1State === 'saturated') {
      if (this.mode !== MODES.BURST) {
        this.transitionTo(MODES.BURST, 'system1_saturated');
      }
      return this.getState();
    }

    // Normal: everything healthy
    if (this.mode !== MODES.NORMAL) {
      this.transitionTo(MODES.NORMAL, 'health_restored');
    }

    return this.getState();
  }

  /**
   * Get the current degrade flags for routing decisions.
   */
  getDegradeFlags() {
    switch (this.mode) {
      case MODES.DEGRADED:
        return {
          tools_disabled: true,
          local_only: true,
          read_only_memory: true,
          deny_reason: this.reason || 'degraded'
        };
      case MODES.RECOVERY:
        return {
          tools_disabled: false,
          local_only: true,
          read_only_memory: false,
          deny_reason: null
        };
      case MODES.BURST:
        return {
          tools_disabled: false,
          local_only: false,
          read_only_memory: false,
          deny_reason: null
        };
      case MODES.NORMAL:
      default:
        return {
          tools_disabled: false,
          local_only: false,
          read_only_memory: false,
          deny_reason: null
        };
    }
  }

  getState() {
    return {
      mode: this.mode,
      entered_at: this.enteredAt,
      reason: this.reason,
      degrade_flags: this.getDegradeFlags(),
      history_length: this.history.length
    };
  }
}

module.exports = {
  MODES,
  DegradedModeController
};
