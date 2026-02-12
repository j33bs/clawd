'use strict';

/**
 * FreeComputeCloud — Quota Ledger
 *
 * Daily rolling quota tracker per-provider. Tracks RPM, RPD, TPM, TPD
 * counters and enforces caps. Reset logic uses conservative local
 * midnight UTC unless provider specifies otherwise.
 *
 * Storage: append-only JSONL (one file per day) for auditability.
 */

const fs = require('node:fs');
const path = require('node:path');

class QuotaLedger {
  /**
   * @param {object} [options]
   * @param {string} [options.ledgerPath] - Directory for ledger files
   * @param {number} [options.resetHour]  - UTC hour for daily reset (0-23)
   * @param {boolean} [options.disabled]  - If true, no disk writes
   */
  constructor(options = {}) {
    this.ledgerPath = options.ledgerPath || '.tmp/quota-ledger';
    this.resetHour = typeof options.resetHour === 'number' ? options.resetHour : 0;
    this.disabled = Boolean(options.disabled);

    // In-memory counters: { provider_id → { rpm, rpd, tpm, tpd, windowStart, dayStart } }
    this._counters = new Map();
    this._minuteWindow = 60000; // 1 minute

    if (!this.disabled) {
      try { fs.mkdirSync(this.ledgerPath, { recursive: true }); } catch (_) { /* best-effort */ }
    }
  }

  /**
   * Record a request for quota tracking.
   * @param {string} providerId
   * @param {object} usage - { tokensIn, tokensOut }
   */
  record(providerId, usage = {}) {
    const now = Date.now();
    const c = this._getOrCreate(providerId, now);

    // Reset minute window if needed
    if (now - c.minuteStart >= this._minuteWindow) {
      c.rpm = 0;
      c.tpm = 0;
      c.minuteStart = now;
    }

    // Reset day window if needed
    if (this._shouldResetDay(c.dayStart, now)) {
      c.rpd = 0;
      c.tpd = 0;
      c.dayStart = now;
    }

    const tokens = (Number(usage.tokensIn) || 0) + (Number(usage.tokensOut) || 0);
    c.rpm += 1;
    c.rpd += 1;
    c.tpm += tokens;
    c.tpd += tokens;

    // Persist
    this._appendEntry(providerId, {
      ts: new Date(now).toISOString(),
      provider_id: providerId,
      event: 'request',
      tokens_in: usage.tokensIn || 0,
      tokens_out: usage.tokensOut || 0,
      rpm: c.rpm,
      rpd: c.rpd,
      tpm: c.tpm,
      tpd: c.tpd
    });
  }

  /**
   * Check whether a request is within quota limits.
   * @param {string} providerId
   * @param {object} caps - { rpm, rpd, tpm, tpd } (from catalog constraints)
   * @returns {{ allowed: boolean, reason?: string, counters: object }}
   */
  check(providerId, caps = {}) {
    const now = Date.now();
    const c = this._getOrCreate(providerId, now);

    // Reset expired windows
    if (now - c.minuteStart >= this._minuteWindow) {
      c.rpm = 0;
      c.tpm = 0;
      c.minuteStart = now;
    }
    if (this._shouldResetDay(c.dayStart, now)) {
      c.rpd = 0;
      c.tpd = 0;
      c.dayStart = now;
    }

    const counters = { rpm: c.rpm, rpd: c.rpd, tpm: c.tpm, tpd: c.tpd };

    if (typeof caps.rpm === 'number' && c.rpm >= caps.rpm) {
      return { allowed: false, reason: 'rpm_exceeded', counters };
    }
    if (typeof caps.rpd === 'number' && c.rpd >= caps.rpd) {
      return { allowed: false, reason: 'rpd_exceeded', counters };
    }
    if (typeof caps.tpm === 'number' && c.tpm >= caps.tpm) {
      return { allowed: false, reason: 'tpm_exceeded', counters };
    }
    if (typeof caps.tpd === 'number' && c.tpd >= caps.tpd) {
      return { allowed: false, reason: 'tpd_exceeded', counters };
    }

    return { allowed: true, counters };
  }

  /**
   * Get snapshot of all counters.
   * @returns {object}
   */
  snapshot() {
    const result = {};
    for (const [providerId, c] of this._counters) {
      result[providerId] = {
        rpm: c.rpm, rpd: c.rpd, tpm: c.tpm, tpd: c.tpd,
        minuteStart: c.minuteStart, dayStart: c.dayStart
      };
    }
    return result;
  }

  /**
   * Reset counters for a specific provider (operator override).
   */
  resetProvider(providerId) {
    this._counters.delete(providerId);
  }

  // ── Internal ────────────────────────────────────────────────────────

  _getOrCreate(providerId, now) {
    if (!this._counters.has(providerId)) {
      this._counters.set(providerId, {
        rpm: 0, rpd: 0, tpm: 0, tpd: 0,
        minuteStart: now,
        dayStart: now
      });
    }
    return this._counters.get(providerId);
  }

  _shouldResetDay(dayStart, now) {
    const startDate = new Date(dayStart);
    const nowDate = new Date(now);
    // Simple: if UTC date has changed
    return startDate.getUTCDate() !== nowDate.getUTCDate()
      || startDate.getUTCMonth() !== nowDate.getUTCMonth()
      || startDate.getUTCFullYear() !== nowDate.getUTCFullYear();
  }

  _appendEntry(providerId, entry) {
    if (this.disabled) return;
    try {
      const dateStr = new Date().toISOString().slice(0, 10);
      const file = path.join(this.ledgerPath, `ledger-${dateStr}.jsonl`);
      fs.appendFileSync(file, JSON.stringify(entry) + '\n', 'utf8');
    } catch (_) {
      // Best-effort; do not crash on ledger write failure
    }
  }
}

module.exports = { QuotaLedger };
