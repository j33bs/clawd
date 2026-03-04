'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

function toNumber(value, fallback = 0) {
  const n = Number(value);
  if (!Number.isFinite(n)) return fallback;
  return n;
}

function toUtcIso(ts = Date.now()) {
  return new Date(ts).toISOString();
}

function hashHex(input) {
  return crypto.createHash('sha256').update(String(input || '')).digest('hex');
}

class TokenUsageLogger {
  constructor(options = {}) {
    const env = options.env || process.env;
    this._env = env;
    this.logPath = env.OPENCLAW_TOKEN_USAGE_LOG_PATH
      ? path.resolve(String(env.OPENCLAW_TOKEN_USAGE_LOG_PATH))
      : path.resolve(process.cwd(), 'workspace', 'logs', 'token_usage.jsonl');
    const rawRate = toNumber(env.OPENCLAW_TOKENLOG_SAMPLE_RATE, 1.0);
    this.sampleRate = Math.max(0, Math.min(1, rawRate));
    this.enabled = String(env.OPENCLAW_TOKENLOG_ENABLED || '1') !== '0';
  }

  shouldSample(requestId) {
    if (!this.enabled) return false;
    if (this.sampleRate >= 1) return true;
    if (this.sampleRate <= 0) return false;
    const digest = hashHex(requestId || 'no_request_id');
    const bucket = parseInt(digest.slice(0, 8), 16) / 0xffffffff;
    return bucket <= this.sampleRate;
  }

  log(entry = {}) {
    const requestId = entry.request_id || entry.requestId || 'unknown';
    if (!this.shouldSample(requestId)) return false;

    const payload = {
      ts_utc: entry.ts_utc || toUtcIso(),
      request_id: requestId,
      agent_id: entry.agent_id || null,
      channel: entry.channel || null,
      provider: entry.provider || null,
      model: entry.model || null,
      reason_tag: entry.reason_tag || null,
      prompt_chars: Math.max(0, Math.floor(toNumber(entry.prompt_chars, 0))),
      tool_output_chars: Math.max(0, Math.floor(toNumber(entry.tool_output_chars, 0))),
      tokens_in: Math.max(0, Math.floor(toNumber(entry.tokens_in, 0))),
      tokens_out: Math.max(0, Math.floor(toNumber(entry.tokens_out, 0))),
      total_tokens: Math.max(0, Math.floor(toNumber(entry.total_tokens, 0))),
      cache_read_tokens: Math.max(0, Math.floor(toNumber(entry.cache_read_tokens, 0))),
      cache_write_tokens: Math.max(0, Math.floor(toNumber(entry.cache_write_tokens, 0))),
      latency_ms: Math.max(0, Math.floor(toNumber(entry.latency_ms, 0))),
      status: entry.status || 'unknown'
    };

    if (entry.prompt_hash) {
      payload.prompt_hash = String(entry.prompt_hash);
    }

    const dir = path.dirname(this.logPath);
    fs.mkdirSync(dir, { recursive: true });
    fs.appendFileSync(this.logPath, `${JSON.stringify(payload)}\n`, 'utf8');
    return true;
  }
}

module.exports = {
  TokenUsageLogger,
  hashHex
};

