'use strict';

/**
 * ConcurrencyTuner — VRAM-aware dynamic max-concurrency for the vLLM provider.
 *
 * Problem
 * -------
 * The catalog hardcodes max_concurrent_requests = 2.  On an RTX 3090 running
 * Qwen2.5-14B AWQ (which uses PagedAttention), the actual safe concurrency
 * depends on how much KV-cache VRAM is available *right now*:
 *
 *   - KV cache fills as concurrent requests accumulate context
 *   - If KV cache is 0% used and VRAM has headroom → safe to push to 6–8
 *   - If KV cache is 80%+ → drop back to 2 to avoid evictions / latency spikes
 *
 * Solution
 * --------
 * ConcurrencyTuner combines two signals:
 *
 *   1. VRAM free headroom from nvidia-smi
 *   2. KV cache usage from the vLLM /metrics endpoint
 *
 * From these it computes a recommended concurrency ceiling [minConcurrency, maxConcurrency]
 * and updates the value used by the LocalVllmProvider at runtime.
 *
 * Integration
 * -----------
 *   const { ConcurrencyTuner } = require('./concurrency_tuner');
 *   const tuner = new ConcurrencyTuner();
 *   await tuner.update();
 *   const limit = tuner.currentLimit();   // use instead of catalog default
 *
 * Or start background auto-tuning:
 *   tuner.start();  // polls every 10s
 *
 * The LocalVllmProvider can inject this as:
 *   const maxConcurrent = tuner ? tuner.currentLimit() : catalogDefault;
 */

const { execFile } = require('node:child_process');
const http  = require('node:http');
const https = require('node:https');
const { URL } = require('node:url');

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const DEFAULTS = {
  minConcurrency:     parseInt(process.env.OPENCLAW_VLLM_MIN_CONCURRENCY  || '2',  10),
  maxConcurrency:     parseInt(process.env.OPENCLAW_VLLM_MAX_CONCURRENCY  || '8',  10),
  targetKvUsagePct:   parseFloat(process.env.OPENCLAW_VLLM_KV_TARGET_PCT  || '60'),
  criticalKvPct:      parseFloat(process.env.OPENCLAW_VLLM_KV_CRITICAL_PCT || '80'),
  vramReserveMib:     parseFloat(process.env.OPENCLAW_VLLM_VRAM_RESERVE_MIB || '512'),
  pollIntervalMs:     parseInt(process.env.OPENCLAW_VLLM_TUNE_POLL_MS     || '10000', 10),
  metricsUrl:         process.env.OPENCLAW_VLLM_METRICS_URL || 'http://127.0.0.1:8001/metrics',
  gpuIndex:           parseInt(process.env.OPENCLAW_GPU_INDEX             || '0', 10),
};

// ---------------------------------------------------------------------------
// nvidia-smi fetch (free VRAM MiB)
// ---------------------------------------------------------------------------

function getVramFreeMib(gpuIndex, timeoutMs = 2500) {
  return new Promise((resolve) => {
    const args = [
      '--query-gpu=index,memory.used,memory.total',
      '--format=csv,noheader,nounits',
    ];
    const timer = setTimeout(() => resolve(null), timeoutMs);
    execFile('nvidia-smi', args, { timeout: timeoutMs }, (err, stdout) => {
      clearTimeout(timer);
      if (err) return resolve(null);
      for (const line of stdout.trim().split('\n')) {
        const parts = line.split(',').map((p) => parseFloat(p.trim()));
        if (parts.length >= 3 && parts[0] === gpuIndex) {
          const [, used, total] = parts;
          resolve(total - used);
          return;
        }
      }
      // fallback: first GPU
      const first = stdout.trim().split('\n')[0];
      if (first) {
        const parts = first.split(',').map((p) => parseFloat(p.trim()));
        if (parts.length >= 3) return resolve(parts[2] - parts[1]);
      }
      resolve(null);
    });
  });
}

// ---------------------------------------------------------------------------
// vLLM /metrics fetch (KV cache usage)
// ---------------------------------------------------------------------------

function fetchMetricsRaw(metricsUrl, timeoutMs = 3000) {
  return new Promise((resolve) => {
    const parsed  = new URL(metricsUrl);
    const isHttps = parsed.protocol === 'https:';
    const mod     = isHttps ? https : http;
    const timer   = setTimeout(() => resolve(null), timeoutMs);

    const req = mod.request({
      hostname: parsed.hostname,
      port:     parsed.port || (isHttps ? 443 : 80),
      path:     parsed.pathname + parsed.search,
      method:   'GET',
      timeout:  timeoutMs,
    }, (res) => {
      let data = '';
      res.on('data', (c) => { data += c; });
      res.on('end', () => { clearTimeout(timer); resolve(data); });
    });
    req.on('error', () => { clearTimeout(timer); resolve(null); });
    req.on('timeout', () => { req.destroy(); resolve(null); });
    req.end();
  });
}

function extractKvCachePct(metricsText) {
  // vllm:kv_cache_usage_perc{...} 0.37
  const match = metricsText && metricsText.match(/vllm:kv_cache_usage_perc\{[^}]*\}\s+([\d.eE+\-]+)/);
  if (!match) return null;
  const val = parseFloat(match[1]);
  return isNaN(val) ? null : val * 100; // convert 0–1 → 0–100
}

function extractQueueDepth(metricsText) {
  const match = metricsText && metricsText.match(/vllm:num_requests_waiting\{[^}]*\}\s+([\d.]+)/);
  if (!match) return 0;
  return parseFloat(match[1]) || 0;
}

// ---------------------------------------------------------------------------
// Compute recommendation
// ---------------------------------------------------------------------------

/**
 * Given telemetry, compute the recommended concurrency ceiling.
 *
 * Logic:
 *   - If KV cache > criticalKvPct → floor at min (avoid evictions)
 *   - If KV cache > targetKvPct   → reduce by 1 step
 *   - If VRAM free < vramReserveMib → cap at min
 *   - Otherwise → allow up to max
 *   - Queue depth > 0 → slightly more aggressive (requests are already waiting)
 *
 * Returns integer in [min, max].
 */
function computeRecommendation({
  kvCachePct,
  vramFreeMib,
  queueDepth,
  minConcurrency,
  maxConcurrency,
  targetKvUsagePct,
  criticalKvPct,
  vramReserveMib,
}) {
  let limit = maxConcurrency;

  // KV cache pressure is the primary signal
  if (kvCachePct !== null) {
    if (kvCachePct >= criticalKvPct) {
      limit = minConcurrency;
    } else if (kvCachePct >= targetKvUsagePct) {
      // Linear interpolation: at target → max-1, at critical → min
      const t = (kvCachePct - targetKvUsagePct) / (criticalKvPct - targetKvUsagePct);
      limit = Math.round(maxConcurrency - 1 - t * (maxConcurrency - 1 - minConcurrency));
    }
  }

  // VRAM headroom guard
  if (vramFreeMib !== null && vramFreeMib < vramReserveMib) {
    limit = Math.min(limit, minConcurrency);
  }

  // If queue is already backing up, don't reduce further (it won't help)
  if (queueDepth > 2 && limit < minConcurrency + 1) {
    limit = minConcurrency + 1;
  }

  return Math.max(minConcurrency, Math.min(maxConcurrency, limit));
}

// ---------------------------------------------------------------------------
// ConcurrencyTuner class
// ---------------------------------------------------------------------------

class ConcurrencyTuner {
  constructor(opts = {}) {
    this.minConcurrency   = opts.minConcurrency   ?? DEFAULTS.minConcurrency;
    this.maxConcurrency   = opts.maxConcurrency   ?? DEFAULTS.maxConcurrency;
    this.targetKvUsagePct = opts.targetKvUsagePct ?? DEFAULTS.targetKvUsagePct;
    this.criticalKvPct    = opts.criticalKvPct    ?? DEFAULTS.criticalKvPct;
    this.vramReserveMib   = opts.vramReserveMib   ?? DEFAULTS.vramReserveMib;
    this.pollIntervalMs   = opts.pollIntervalMs   ?? DEFAULTS.pollIntervalMs;
    this.metricsUrl       = opts.metricsUrl       ?? DEFAULTS.metricsUrl;
    this.gpuIndex         = opts.gpuIndex         ?? DEFAULTS.gpuIndex;

    this._limit  = this.minConcurrency; // conservative start
    this._lastTs = 0;
    this._lastTelemetry = null;
    this._timer  = null;
  }

  // -------------------------------------------------------------------------
  // Background polling
  // -------------------------------------------------------------------------

  start() {
    if (this._timer) return this;
    this.update().catch(() => {});
    this._timer = setInterval(() => this.update().catch(() => {}), this.pollIntervalMs);
    if (this._timer.unref) this._timer.unref();
    return this;
  }

  stop() {
    if (this._timer) { clearInterval(this._timer); this._timer = null; }
    return this;
  }

  // -------------------------------------------------------------------------
  // Manual update
  // -------------------------------------------------------------------------

  async update() {
    const [vramFree, metricsText] = await Promise.all([
      getVramFreeMib(this.gpuIndex),
      fetchMetricsRaw(this.metricsUrl),
    ]);

    const kvCachePct = metricsText ? extractKvCachePct(metricsText) : null;
    const queueDepth = metricsText ? extractQueueDepth(metricsText) : 0;

    const recommendation = computeRecommendation({
      kvCachePct,
      vramFreeMib:    vramFree,
      queueDepth,
      minConcurrency: this.minConcurrency,
      maxConcurrency: this.maxConcurrency,
      targetKvUsagePct: this.targetKvUsagePct,
      criticalKvPct:    this.criticalKvPct,
      vramReserveMib:   this.vramReserveMib,
    });

    this._limit = recommendation;
    this._lastTs = Date.now();
    this._lastTelemetry = {
      kvCachePct:  kvCachePct !== null ? Math.round(kvCachePct * 10) / 10 : null,
      vramFreeMib: vramFree   !== null ? Math.round(vramFree)             : null,
      queueDepth,
      recommendedLimit: recommendation,
    };

    return recommendation;
  }

  // -------------------------------------------------------------------------
  // Public API
  // -------------------------------------------------------------------------

  /** Current recommended concurrency ceiling. */
  currentLimit() {
    return this._limit;
  }

  /** Last telemetry snapshot used to compute the limit. */
  telemetry() {
    return this._lastTelemetry ? { ...this._lastTelemetry, computedAt: this._lastTs } : null;
  }
}

// ---------------------------------------------------------------------------
// Module-level singleton
// ---------------------------------------------------------------------------

let _defaultTuner = null;

function getDefaultTuner(opts = {}) {
  if (!_defaultTuner) _defaultTuner = new ConcurrencyTuner(opts);
  return _defaultTuner;
}

module.exports = { ConcurrencyTuner, getDefaultTuner, computeRecommendation };
