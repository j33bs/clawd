'use strict';

const { stableStringify } = require('../canonical_json');

function deterministicBackoffMs(attemptIndex, options = {}) {
  const baseMs = Number.isFinite(options.baseMs) ? options.baseMs : 250;
  const capMs = Number.isFinite(options.capMs) ? options.capMs : 2000;
  const pow = Math.pow(2, Math.max(0, attemptIndex));
  return Math.min(capMs, baseMs * pow);
}

async function defaultSleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Transport contract (no network in Phase 2):
 * transport.send(bytes, { contentType }) -> Promise<{ ok: boolean }>
 */
async function sendEnvelope(envelope, transport, options = {}) {
  if (!options.enabled) {
    const err = new Error('federation transport disabled');
    err.code = 'FEDERATION_DISABLED';
    throw err;
  }
  if (!transport || typeof transport.send !== 'function') {
    const err = new Error('transport missing');
    err.code = 'TRANSPORT_MISSING';
    throw err;
  }

  const maxAttempts = Number.isFinite(options.maxAttempts) ? options.maxAttempts : 1;
  const sleep = options.sleepFn || defaultSleep;
  const bytes = Buffer.from(stableStringify(envelope), 'utf8');

  let lastErr = null;
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      const res = await transport.send(bytes, { contentType: 'application/json' });
      if (res && res.ok === true) return res;
      const err = new Error('transport send failed');
      err.code = 'TRANSPORT_SEND_FAILED';
      throw err;
    } catch (err) {
      lastErr = err;
      if (attempt + 1 >= maxAttempts) break;
      const delay = deterministicBackoffMs(attempt, options.backoff || {});
      await sleep(delay);
    }
  }
  throw lastErr;
}

module.exports = {
  deterministicBackoffMs,
  sendEnvelope
};

