'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const FORBIDDEN_KEYS = new Set(['prompt', 'text', 'body', 'content', 'document_body', 'raw_content', 'raw']);

function nowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
}

function sanitize(value) {
  if (Array.isArray(value)) return value.map((v) => sanitize(v));
  if (value && typeof value === 'object') {
    const out = {};
    for (const [k, v] of Object.entries(value)) {
      if (FORBIDDEN_KEYS.has(String(k).trim().toLowerCase())) continue;
      out[String(k)] = sanitize(v);
    }
    return out;
  }
  return value;
}

function estimateWeight(update) {
  const message = update && update.message && typeof update.message === 'object' ? update.message : {};
  const text = typeof message.text === 'string' ? message.text : '';
  const caption = typeof message.caption === 'string' ? message.caption : '';
  const photoCount = Array.isArray(message.photo) ? message.photo.length : 0;
  const hasDocument = Boolean(message.document);
  const hasMedia = photoCount > 0 || hasDocument || Boolean(message.video) || Boolean(message.audio);
  const chars = text.length + caption.length;
  const mediaWeight = hasMedia ? 2500 : 0;
  return { chars, hasMedia, mediaWeight, total: chars + mediaWeight };
}

function shouldDefer(update, opts = {}) {
  const threshold = Number(opts.threshold || process.env.OPENCLAW_TELEGRAM_DEFER_THRESHOLD || 2200);
  const w = estimateWeight(update);
  if (w.hasMedia) return { defer: true, reason: 'media_payload', estimate: w.total };
  if (w.total > threshold) return { defer: true, reason: 'payload_large', estimate: w.total };
  return { defer: false, reason: 'inline_ok', estimate: w.total };
}

function fastAck(update, opts = {}) {
  const corrId = String(opts.corrId || `tg_${Date.now()}`);
  const d = shouldDefer(update, opts);
  return {
    statusCode: 200,
    body: {
      ok: true,
      corr_id: corrId,
      deferred: d.defer,
      defer_reason: d.reason,
      ts: nowIso()
    }
  };
}

async function withRetry(fn, opts = {}) {
  const retries = Math.max(0, Number(opts.retries == null ? 2 : opts.retries));
  const baseDelayMs = Math.max(0, Number(opts.baseDelayMs == null ? 100 : opts.baseDelayMs));
  const isRetryable = typeof opts.isRetryable === 'function'
    ? opts.isRetryable
    : () => true;
  let attempt = 0;
  let lastErr = null;
  while (attempt <= retries) {
    try {
      return await fn(attempt);
    } catch (err) {
      lastErr = err;
      if (attempt >= retries || !isRetryable(err)) break;
      const delay = Math.min(2000, baseDelayMs * Math.pow(2, attempt));
      await new Promise((resolve) => setTimeout(resolve, delay));
      attempt += 1;
    }
  }
  throw lastErr || new Error('telegram_retry_failed');
}

function deadletterPath(env = process.env) {
  return env.OPENCLAW_TELEGRAM_DEADLETTER_PATH
    || path.join(os.homedir(), '.local', 'share', 'openclaw', 'telegram', 'deadletter.jsonl');
}

function writeDeadletter(meta, env = process.env) {
  const target = deadletterPath(env);
  const line = {
    ts: nowIso(),
    corr_id: String((meta && meta.corr_id) || ''),
    reason: String((meta && meta.reason) || 'unknown'),
    envelope: sanitize(meta || {}),
    redaction_mode: 'metadata_only'
  };
  try {
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.appendFileSync(target, `${JSON.stringify(line)}\n`, 'utf8');
    return { ok: true, path: target };
  } catch (err) {
    return { ok: false, path: target, reason: (err && (err.code || err.name)) || 'error' };
  }
}

module.exports = {
  shouldDefer,
  fastAck,
  withRetry,
  writeDeadletter
};
