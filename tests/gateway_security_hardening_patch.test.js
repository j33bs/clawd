import test from 'node:test';
import assert from 'node:assert/strict';

import {
  applyGatewaySecurityHardeningPatch,
  createAuthAttemptLimiter,
  isOriginAllowed,
  normalizeAllowedOrigins
} from '../tools/gateway_security_hardening_patch.mjs';

test('normalizeAllowedOrigins rejects wildcard and non-http(s) origins', () => {
  const result = normalizeAllowedOrigins([
    ' https://good.example ',
    'https://*.ts.net',
    'ws://localhost:18789',
    '',
    'http://localhost:18789'
  ]);

  assert.deepEqual(result.normalized, ['https://good.example', 'http://localhost:18789']);
  assert.equal(
    result.rejected.some((entry) => entry.reason === 'wildcard' && entry.value === 'https://*.ts.net'),
    true
  );
  assert.equal(
    result.rejected.some((entry) => entry.reason === 'invalid-scheme' && entry.value === 'ws://localhost:18789'),
    true
  );
});

test('isOriginAllowed blocks cross-origin when allowedOrigins is empty', () => {
  assert.equal(
    isOriginAllowed({
      origin: 'https://evil.example',
      allowedOrigins: [],
      requestHost: 'dali.ts.net',
      allowHostHeaderOriginFallback: false,
      nodeEnv: 'production'
    }),
    false
  );
});

test('isOriginAllowed allows only explicit allowlist entries', () => {
  assert.equal(
    isOriginAllowed({
      origin: 'https://good.example',
      allowedOrigins: ['https://good.example'],
      requestHost: 'dali.ts.net',
      allowHostHeaderOriginFallback: false,
      nodeEnv: 'production'
    }),
    true
  );
  assert.equal(
    isOriginAllowed({
      origin: 'https://evil.example',
      allowedOrigins: ['https://good.example'],
      requestHost: 'dali.ts.net',
      allowHostHeaderOriginFallback: false,
      nodeEnv: 'production'
    }),
    false
  );
});

test('auth limiter allows maxAttempts, blocks maxAttempts+1, resets after window', () => {
  let nowMs = 1_000;
  const limiter = createAuthAttemptLimiter({ maxAttempts: 3, windowMs: 1_000 }, () => nowMs);
  const key = '198.51.100.10';

  assert.equal(limiter.check(key).allowed, true);
  limiter.recordFailure(key);
  assert.equal(limiter.check(key).allowed, true);
  limiter.recordFailure(key);
  assert.equal(limiter.check(key).allowed, true);
  limiter.recordFailure(key);

  assert.equal(limiter.check(key).allowed, false);

  nowMs += 1_001;
  assert.equal(limiter.check(key).allowed, true);
});

test('applyGatewaySecurityHardeningPatch injects origin and rate-limit hardening blocks', () => {
  const fixture = `function parseOrigin(originRaw) {
\tconst trimmed = (originRaw ?? "").trim();
\tif (!trimmed || trimmed === "null") return null;
\ttry {
\t\tconst url = new URL(trimmed);
\t\treturn {
\t\t\torigin: url.origin.toLowerCase(),
\t\t\thost: url.host.toLowerCase(),
\t\t\thostname: url.hostname.toLowerCase()
\t\t};
\t} catch {
\t\treturn null;
\t}
}
function checkBrowserOrigin(params) {
\tconst parsedOrigin = parseOrigin(params.origin);
\tif (!parsedOrigin) return {
\t\tok: false,
\t\treason: "origin missing or invalid"
\t};
\tif ((params.allowedOrigins ?? []).map((value) => value.trim().toLowerCase()).filter(Boolean).includes(parsedOrigin.origin)) return { ok: true };
\tconst requestHost = normalizeHostHeader(params.requestHost);
\tif (params.allowHostHeaderOriginFallback === true && requestHost && parsedOrigin.host === requestHost) return { ok: true };
\tconst requestHostname = resolveHostName(requestHost);
\tif (isLoopbackHost(parsedOrigin.hostname) && isLoopbackHost(requestHostname)) return { ok: true };
\treturn {
\t\tok: false,
\t\treason: "origin not allowed"
\t};
}

//#endregion
const trustedProxies = params.cfg.gateway?.trustedProxies ?? [];
\tconst controlUiAllowedOrigins = (params.cfg.gateway?.controlUi?.allowedOrigins ?? []).map((value) => value.trim()).filter(Boolean);
\tconst dangerouslyAllowHostHeaderOriginFallback = params.cfg.gateway?.controlUi?.dangerouslyAllowHostHeaderOriginFallback === true;
function createGatewayAuthRateLimiters(rateLimitConfig) {
\treturn {
\t\trateLimiter: rateLimitConfig ? createAuthRateLimiter(rateLimitConfig) : void 0,
\t\tbrowserRateLimiter: createAuthRateLimiter({
\t\t\t...rateLimitConfig,
\t\t\texemptLoopback: false
\t\t})
\t};
}`;

  const patched = applyGatewaySecurityHardeningPatch(fixture);
  assert.equal(patched.includes('normalizeConfiguredAllowedOrigins'), true);
  assert.equal(patched.includes('gateway.controlUi.allowedOrigins rejects wildcard patterns'), true);
  assert.equal(patched.includes('normalizedRateLimitConfig'), true);
});
