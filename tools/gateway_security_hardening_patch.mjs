#!/usr/bin/env node
import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';

const ORIGIN_BLOCK_RE =
  /function parseOrigin\(originRaw\) \{[\s\S]*?function checkBrowserOrigin\(params\) \{[\s\S]*?\n\}\n\n\/\/#endregion/;

const CONTROL_UI_CONFIG_BLOCK_RE =
  /const trustedProxies = params\.cfg\.gateway\?\.trustedProxies \?\? \[\];\n\tconst controlUiAllowedOrigins = \(params\.cfg\.gateway\?\.controlUi\?\.allowedOrigins \?\? \[\]\)\.map\(\(value\) => value\.trim\(\)\)\.filter\(Boolean\);\n\tconst dangerouslyAllowHostHeaderOriginFallback = params\.cfg\.gateway\?\.controlUi\?\.dangerouslyAllowHostHeaderOriginFallback === true;/;

const RATE_LIMITER_BLOCK_RE =
  /function createGatewayAuthRateLimiters\(rateLimitConfig\) \{\n\treturn \{\n\t\trateLimiter: rateLimitConfig \? createAuthRateLimiter\(rateLimitConfig\) : void 0,\n\t\tbrowserRateLimiter: createAuthRateLimiter\(\{\n\t\t\t\.\.\.rateLimitConfig,\n\t\t\texemptLoopback: false\n\t\t\}\)\n\t\};\n\}/;

const ORIGIN_BLOCK_REPLACEMENT = `function parseOrigin(originRaw) {
\tconst trimmed = (originRaw ?? "").trim();
\tif (!trimmed || trimmed === "null") return null;
\ttry {
\t\tconst url = new URL(trimmed);
\t\tconst protocol = url.protocol.toLowerCase();
\t\tif (protocol !== "http:" && protocol !== "https:") return null;
\t\treturn {
\t\t\torigin: url.origin.toLowerCase(),
\t\t\thost: url.host.toLowerCase(),
\t\t\thostname: url.hostname.toLowerCase()
\t\t};
\t} catch {
\t\treturn null;
\t}
}
function normalizeConfiguredAllowedOrigins(values) {
\tconst normalized = [];
\tfor (const value of values ?? []) {
\t\tconst raw = String(value ?? "").trim();
\t\tif (!raw) continue;
\t\tif (raw.includes("*")) continue;
\t\ttry {
\t\t\tconst parsed = new URL(raw);
\t\t\tconst protocol = parsed.protocol.toLowerCase();
\t\t\tif (protocol !== "http:" && protocol !== "https:") continue;
\t\t\tnormalized.push(parsed.origin.toLowerCase());
\t\t} catch {}
\t}
\treturn normalized;
}
function isDevOrTestNodeEnv(envName) {
\tconst normalized = String(envName ?? process.env.NODE_ENV ?? "").trim().toLowerCase();
\treturn normalized === "development" || normalized === "test";
}
function checkBrowserOrigin(params) {
\tconst parsedOrigin = parseOrigin(params.origin);
\tif (!parsedOrigin) return {
\t\tok: false,
\t\treason: "origin missing or invalid"
\t};
\tconst allowedOrigins = normalizeConfiguredAllowedOrigins(params.allowedOrigins);
\tif (allowedOrigins.includes(parsedOrigin.origin)) return { ok: true };
\tconst requestHost = normalizeHostHeader(params.requestHost);
\tif (params.allowHostHeaderOriginFallback === true && requestHost && parsedOrigin.host === requestHost) return { ok: true };
\tconst requestHostname = resolveHostName(requestHost);
\tif (isLoopbackHost(parsedOrigin.hostname) && isLoopbackHost(requestHostname)) return { ok: true };
\tif (allowedOrigins.length === 0 && isDevOrTestNodeEnv(params.nodeEnv) && isLoopbackHost(parsedOrigin.hostname)) return { ok: true };
\treturn {
\t\tok: false,
\t\treason: "origin not allowed"
\t};
}

//#endregion`;

const CONTROL_UI_CONFIG_BLOCK_REPLACEMENT = `const trustedProxies = params.cfg.gateway?.trustedProxies ?? [];
\tconst controlUiAllowedOriginsRaw = params.cfg.gateway?.controlUi?.allowedOrigins ?? [];
\tconst controlUiAllowedOrigins = controlUiAllowedOriginsRaw.map((value) => String(value ?? "").trim()).filter(Boolean);
\tfor (const origin of controlUiAllowedOrigins) {
\t\tif (origin.includes("*")) throw new Error(\`gateway.controlUi.allowedOrigins rejects wildcard patterns (\${origin})\`);
\t\tlet parsedOrigin;
\t\ttry {
\t\t\tparsedOrigin = new URL(origin);
\t\t} catch {
\t\t\tthrow new Error(\`gateway.controlUi.allowedOrigins must contain valid URL origins (\${origin})\`);
\t\t}
\t\tconst protocol = parsedOrigin.protocol.toLowerCase();
\t\tif (protocol !== "http:" && protocol !== "https:") throw new Error(\`gateway.controlUi.allowedOrigins supports only http(s) origins (\${origin})\`);
\t}
\tconst dangerouslyAllowHostHeaderOriginFallback = params.cfg.gateway?.controlUi?.dangerouslyAllowHostHeaderOriginFallback === true;`;

const RATE_LIMITER_BLOCK_REPLACEMENT = `function createGatewayAuthRateLimiters(rateLimitConfig) {
\tconst normalizedRateLimitConfig = {
\t\tmaxAttempts: 10,
\t\twindowMs: 6e4,
\t\t...(rateLimitConfig ?? {})
\t};
\treturn {
\t\trateLimiter: createAuthRateLimiter(normalizedRateLimitConfig),
\t\tbrowserRateLimiter: createAuthRateLimiter({
\t\t\t...normalizedRateLimitConfig,
\t\t\texemptLoopback: false
\t\t})
\t};
}`;

function replaceOnce(text, pattern, replacement, label) {
  if (!pattern.test(text)) {
    throw new Error(`patch target not found: ${label}`);
  }
  return text.replace(pattern, replacement);
}

export function applyGatewaySecurityHardeningPatch(text) {
  let next = String(text);
  next = replaceOnce(next, ORIGIN_BLOCK_RE, ORIGIN_BLOCK_REPLACEMENT, 'origin-check block');
  next = replaceOnce(
    next,
    CONTROL_UI_CONFIG_BLOCK_RE,
    CONTROL_UI_CONFIG_BLOCK_REPLACEMENT,
    'control-ui config block'
  );
  next = replaceOnce(
    next,
    RATE_LIMITER_BLOCK_RE,
    RATE_LIMITER_BLOCK_REPLACEMENT,
    'gateway auth rate limiter block'
  );
  return next;
}

export function normalizeAllowedOrigins(rawOrigins) {
  const normalized = [];
  const rejected = [];
  for (const raw of rawOrigins ?? []) {
    const value = String(raw ?? '').trim();
    if (!value) {
      rejected.push({ value, reason: 'empty' });
      continue;
    }
    if (value.includes('*')) {
      rejected.push({ value, reason: 'wildcard' });
      continue;
    }
    let parsed;
    try {
      parsed = new URL(value);
    } catch {
      rejected.push({ value, reason: 'invalid-url' });
      continue;
    }
    const protocol = parsed.protocol.toLowerCase();
    if (protocol !== 'http:' && protocol !== 'https:') {
      rejected.push({ value, reason: 'invalid-scheme' });
      continue;
    }
    normalized.push(parsed.origin.toLowerCase());
  }
  return { normalized, rejected };
}

function parseOrigin(raw) {
  try {
    const parsed = new URL(String(raw ?? '').trim());
    if (!['http:', 'https:'].includes(parsed.protocol.toLowerCase())) return null;
    return {
      origin: parsed.origin.toLowerCase(),
      host: parsed.host.toLowerCase(),
      hostname: parsed.hostname.toLowerCase()
    };
  } catch {
    return null;
  }
}

export function isOriginAllowed(params) {
  const parsedOrigin = parseOrigin(params.origin);
  if (!parsedOrigin) return false;
  const { normalized } = normalizeAllowedOrigins(params.allowedOrigins ?? []);
  if (normalized.includes(parsedOrigin.origin)) return true;
  if (params.allowHostHeaderOriginFallback) {
    const reqHost = String(params.requestHost ?? '').trim().toLowerCase();
    if (reqHost && parsedOrigin.host === reqHost) return true;
  }
  const loopbackHostnames = new Set(['localhost', '127.0.0.1', '::1']);
  const originIsLoopback = loopbackHostnames.has(parsedOrigin.hostname);
  const requestHostName = String(params.requestHost ?? '')
    .trim()
    .toLowerCase()
    .replace(/^\[|\]$/g, '')
    .split(':')[0];
  const requestIsLoopback = loopbackHostnames.has(requestHostName);
  if (originIsLoopback && requestIsLoopback) return true;
  if (
    normalized.length === 0 &&
    (String(params.nodeEnv ?? '').toLowerCase() === 'development' ||
      String(params.nodeEnv ?? '').toLowerCase() === 'test') &&
    originIsLoopback
  ) {
    return true;
  }
  return false;
}

export function createAuthAttemptLimiter(config = {}, nowFn = () => Date.now()) {
  const maxAttempts = Number.isInteger(config.maxAttempts) && config.maxAttempts > 0 ? config.maxAttempts : 10;
  const windowMs = Number.isInteger(config.windowMs) && config.windowMs > 0 ? config.windowMs : 60_000;
  const failures = new Map();
  let _hitCount = 0;

  function prune(clientKey, nowMs) {
    const bucket = failures.get(clientKey);
    if (!bucket) return [];
    const cutoff = nowMs - windowMs;
    const next = bucket.filter((ts) => ts > cutoff);
    if (next.length === 0) failures.delete(clientKey);
    else failures.set(clientKey, next);
    return next;
  }

  return {
    check(clientKey) {
      const nowMs = nowFn();
      const bucket = prune(clientKey, nowMs);
      const allowed = bucket.length < maxAttempts;
      if (!allowed) _hitCount += 1;
      return {
        allowed,
        remaining: Math.max(0, maxAttempts - bucket.length)
      };
    },
    recordFailure(clientKey) {
      const nowMs = nowFn();
      const bucket = prune(clientKey, nowMs);
      bucket.push(nowMs);
      failures.set(clientKey, bucket);
      return bucket.length;
    },
    reset(clientKey) {
      failures.delete(clientKey);
    },
    /**
     * Return observability metrics for this limiter instance.
     * CSA CCM v4 LOG-02, LOG-06.
     *
     * @returns {{ rate_limit_hits_total: number, rate_limit_active_windows: number, ts: number }}
     */
    getMetrics() {
      return {
        rate_limit_hits_total: _hitCount,
        rate_limit_active_windows: failures.size,
        ts: Date.now()
      };
    }
  };
}

export function isPatched(text) {
  const source = String(text);
  return (
    source.includes('normalizeConfiguredAllowedOrigins') &&
    source.includes('gateway.controlUi.allowedOrigins rejects wildcard patterns') &&
    source.includes('normalizedRateLimitConfig')
  );
}

async function runCli() {
  const args = process.argv.slice(2);
  const checkOnly = args.includes('--check');
  const fileArgIndex = args.findIndex((arg) => arg === '--file');
  if (fileArgIndex === -1 || !args[fileArgIndex + 1]) {
    throw new Error('usage: gateway_security_hardening_patch.mjs --file <gateway-cli.js> [--check]');
  }
  const targetFile = path.resolve(args[fileArgIndex + 1]);
  const original = await fs.readFile(targetFile, 'utf8');
  if (checkOnly) {
    if (!isPatched(original)) {
      throw new Error(`security hardening patch missing: ${targetFile}`);
    }
    process.stdout.write(`PATCH_OK ${targetFile}\n`);
    return;
  }

  if (isPatched(original)) {
    process.stdout.write(`PATCH_NOOP ${targetFile}\n`);
    return;
  }

  const patched = applyGatewaySecurityHardeningPatch(original);
  if (patched !== original) {
    await fs.writeFile(targetFile, patched, 'utf8');
    process.stdout.write(`PATCH_APPLIED ${targetFile}\n`);
  } else {
    process.stdout.write(`PATCH_NOOP ${targetFile}\n`);
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runCli().catch((error) => {
    process.stderr.write(`${error.message}\n`);
    process.exit(1);
  });
}
