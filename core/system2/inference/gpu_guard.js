'use strict';

/**
 * GPU Guard — VRAM-pressure circuit breaker for the vLLM provider.
 *
 * Problem
 * -------
 * When the RTX 3090's 24 GB VRAM fills up (vLLM + Xorg + browser), new
 * inference requests trigger CUDA OOM errors that crash the EngineCore
 * process.  The existing catalog circuit breaker only trips on HTTP errors
 * — it can't see VRAM pressure building *before* the crash.
 *
 * Solution
 * --------
 * GpuGuard polls nvidia-smi every `pollIntervalMs` and exposes:
 *
 *   guard.shouldDeflect()   → Boolean — true when VRAM > criticalPct
 *   guard.snapshot()        → current telemetry dict
 *   guard.start() / .stop() → begin/end background polling
 *
 * The LocalVllmProvider (or the router) calls shouldDeflect() before
 * dispatching; if true, throws a structured error that the router's
 * circuit breaker interprets as "local unavailable, try cloud fallback".
 *
 * Error shape for router compatibility
 * -------------------------------------
 *   const err = new Error('gpu_vram_pressure');
 *   err.code        = 'GPU_PRESSURE';
 *   err.statusCode  = 503;   // treated same as server overload
 *   err.vramPct     = 94.2;
 *
 * Usage
 * -----
 *   const { GpuGuard, getDefaultGuard } = require('./gpu_guard');
 *
 *   // Module-level singleton (recommended):
 *   const guard = getDefaultGuard();
 *   guard.start();
 *
 *   // In LocalVllmProvider.generateChat():
 *   if (guard.shouldDeflect()) {
 *     const err = guard.makeDeflectError();
 *     throw err;
 *   }
 */

const { execFile } = require('node:child_process');

// ---------------------------------------------------------------------------
// Defaults (all overridable)
// ---------------------------------------------------------------------------
const DEFAULTS = {
  criticalVramPct:    parseFloat(process.env.OPENCLAW_GPU_CRITICAL_VRAM_PCT || '92'),
  warnVramPct:        parseFloat(process.env.OPENCLAW_GPU_WARN_VRAM_PCT     || '85'),
  pollIntervalMs:     parseInt(  process.env.OPENCLAW_GPU_POLL_MS           || '3000', 10),
  nvidiaSmiTimeoutMs: 2500,
  gpuIndex:           parseInt(  process.env.OPENCLAW_GPU_INDEX             || '0',    10),
};

// nvidia-smi query fields — must match _parseNvidiaSmiLine()
const NVIDIA_QUERY = [
  'index',
  'memory.used',
  'memory.total',
  'utilization.gpu',
  'temperature.gpu',
  'power.draw',
  'power.limit',
].join(',');

// ---------------------------------------------------------------------------
// Parser
// ---------------------------------------------------------------------------

function _parseNvidiaSmiLine(line) {
  // Format: "0, 22908 MiB, 24576 MiB, 3, 33, 79.10 W, 350.00 W"
  // (spaces around values because nvidia-smi pads them)
  const parts = line.split(',').map((p) => parseFloat(p.trim())).filter((v) => !isNaN(v));
  if (parts.length < 5) return null;
  const [idx, vramUsed, vramTotal, util, temp, powerDraw, powerLimit] = parts;

  const vramPct  = vramTotal > 0 ? (vramUsed / vramTotal) * 100 : 0;
  const powerPct = (powerLimit > 0) ? (powerDraw / powerLimit) * 100 : 0;

  return {
    gpuIndex:    idx,
    vramUsedMib: vramUsed,
    vramTotalMib: vramTotal,
    vramPct:     Math.round(vramPct * 100) / 100,
    utilizationPct: util,
    temperatureC:   temp,
    powerW:         powerDraw  || 0,
    powerLimitW:    powerLimit || 350,
    powerPct:       Math.round(powerPct * 100) / 100,
  };
}

function _runNvidiaSmi(gpuIndex, timeoutMs) {
  return new Promise((resolve) => {
    const args = [
      `--query-gpu=${NVIDIA_QUERY}`,
      '--format=csv,noheader,nounits',
    ];
    const timer = setTimeout(() => resolve(null), timeoutMs);
    execFile('nvidia-smi', args, { timeout: timeoutMs }, (err, stdout) => {
      clearTimeout(timer);
      if (err) return resolve(null);
      const lines = stdout.trim().split('\n');
      const target = lines
        .map(_parseNvidiaSmiLine)
        .filter(Boolean)
        .find((s) => s.gpuIndex === gpuIndex)
        || lines.map(_parseNvidiaSmiLine).filter(Boolean)[0]
        || null;
      resolve(target);
    });
  });
}

// ---------------------------------------------------------------------------
// GpuGuard class
// ---------------------------------------------------------------------------

class GpuGuard {
  /**
   * @param {object} [opts]
   * @param {number} [opts.criticalVramPct=92]   Deflect requests above this VRAM %.
   * @param {number} [opts.warnVramPct=85]        Emit warnings above this VRAM %.
   * @param {number} [opts.pollIntervalMs=3000]   Polling cadence.
   * @param {number} [opts.gpuIndex=0]            Which GPU to monitor.
   */
  constructor(opts = {}) {
    this.criticalVramPct    = opts.criticalVramPct    ?? DEFAULTS.criticalVramPct;
    this.warnVramPct        = opts.warnVramPct        ?? DEFAULTS.warnVramPct;
    this.pollIntervalMs     = opts.pollIntervalMs     ?? DEFAULTS.pollIntervalMs;
    this.nvidiaSmiTimeoutMs = opts.nvidiaSmiTimeoutMs ?? DEFAULTS.nvidiaSmiTimeoutMs;
    this.gpuIndex           = opts.gpuIndex           ?? DEFAULTS.gpuIndex;

    this._snap   = null;   // last GpuSnapshot
    this._ts     = 0;      // epoch ms of last poll
    this._timer  = null;
    this._polling = false;
  }

  // -------------------------------------------------------------------------
  // Background polling
  // -------------------------------------------------------------------------

  start() {
    if (this._polling) return this;
    this._polling = true;
    this._poll(); // immediate first poll
    this._timer = setInterval(() => this._poll(), this.pollIntervalMs);
    if (this._timer.unref) this._timer.unref(); // don't block process exit
    return this;
  }

  stop() {
    if (this._timer) { clearInterval(this._timer); this._timer = null; }
    this._polling = false;
    return this;
  }

  async _poll() {
    const snap = await _runNvidiaSmi(this.gpuIndex, this.nvidiaSmiTimeoutMs);
    if (snap) {
      this._snap = snap;
      this._ts   = Date.now();
      if (snap.vramPct >= this.criticalVramPct) {
        console.warn(`[gpu_guard] CRITICAL VRAM ${snap.vramPct.toFixed(1)}% — deflecting new requests`);
      } else if (snap.vramPct >= this.warnVramPct) {
        console.warn(`[gpu_guard] WARN VRAM ${snap.vramPct.toFixed(1)}%`);
      }
    }
  }

  // -------------------------------------------------------------------------
  // Public API
  // -------------------------------------------------------------------------

  /** Return the last telemetry snapshot (may be null if never polled). */
  snapshot() {
    if (!this._snap) return null;
    return {
      ...this._snap,
      snapshotAgeMs: Date.now() - this._ts,
      criticalVramPct: this.criticalVramPct,
      warnVramPct: this.warnVramPct,
    };
  }

  /**
   * True when VRAM pressure is above critical threshold.
   * Returns false if telemetry is unavailable (fail-open: don't block requests
   * when we can't measure — the existing HTTP circuit breaker will catch OOM).
   */
  shouldDeflect() {
    if (!this._snap) return false;
    // Stale snapshot (> 3× poll interval) → don't deflect — might be stale high reading
    if (Date.now() - this._ts > this.pollIntervalMs * 3) return false;
    return this._snap.vramPct >= this.criticalVramPct;
  }

  /** True when VRAM is elevated but not yet critical. */
  isWarning() {
    if (!this._snap) return false;
    return this._snap.vramPct >= this.warnVramPct && this._snap.vramPct < this.criticalVramPct;
  }

  /**
   * Build a structured error for the router circuit breaker to handle.
   * Mimics an HTTP 503 so the existing backoff/fallback logic kicks in.
   */
  makeDeflectError() {
    const snap = this._snap;
    const err  = new Error(
      `gpu_vram_pressure: VRAM ${snap ? snap.vramPct.toFixed(1) : '?'}% >= critical ${this.criticalVramPct}%`
    );
    err.code       = 'GPU_PRESSURE';
    err.statusCode = 503;
    err.vramPct    = snap ? snap.vramPct : null;
    return err;
  }

  /**
   * Normalize VRAM pressure to [0, 1] for arousal system integration.
   * 0 = idle, 1 = at or above critical threshold.
   */
  pressureNormalized() {
    if (!this._snap) return 0;
    return Math.min(1, this._snap.vramPct / this.criticalVramPct);
  }
}

// ---------------------------------------------------------------------------
// Module-level singleton
// ---------------------------------------------------------------------------

let _defaultGuard = null;

function getDefaultGuard(opts = {}) {
  if (!_defaultGuard) {
    _defaultGuard = new GpuGuard(opts);
  }
  return _defaultGuard;
}

module.exports = { GpuGuard, getDefaultGuard };
