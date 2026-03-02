import { inspect } from 'node:util';

const LEVEL_WEIGHT = Object.freeze({
  trace: 10,
  debug: 20,
  info: 30,
  warn: 40,
  error: 50,
  fatal: 60,
  silent: 70
});

function normalizeLogLevel(value, fallback = 'info') {
  const normalized = String(value || '').trim().toLowerCase();
  return Object.hasOwn(LEVEL_WEIGHT, normalized) ? normalized : fallback;
}

function serializeError(error) {
  if (!(error instanceof Error)) return error;
  return {
    type: error.name,
    message: error.message,
    stack: error.stack
  };
}

// Sensitive key patterns for object-key redaction (Phase 5, DSP-07).
const SENSITIVE_KEY_RE = /key|secret|password|token|credential|auth/i;

function redactString(value) {
  let out = String(value);
  // Bearer / Authorization header values.
  out = out.replace(/(authorization\s*:\s*bearer\s+)[^\s,;]+/gi, '$1<redacted>');
  out = out.replace(/\bBearer\s+[A-Za-z0-9._~+\-/=]{8,}/g, 'Bearer <redacted>');
  // Basic auth header values (base64 after "Basic ").
  out = out.replace(/(authorization\s*:\s*basic\s+)[A-Za-z0-9+/=]{10,}/gi, '$1<redacted>');
  // Any OPENCLAW_ env var assignment (OPENCLAW_FOO=value) — run before generic patterns.
  out = out.replace(/\bOPENCLAW_[A-Z_]+=\S+/g, (m) => {
    const eqIdx = m.indexOf('=');
    return m.slice(0, eqIdx + 1) + '<redacted>';
  });
  // Generic key=value / key: value patterns for known sensitive field names.
  // Run BEFORE specific token-prefix patterns so the generic pass doesn't
  // clobber the more specific <redacted-token> markers on a second pass.
  out = out.replace(/((?:api[_-]?key|token|secret|password)\s*[:=]\s*)([^\s,;]+)/gi, '$1<redacted>');
  // Specific token prefixes — catch standalone tokens not in key=value context.
  // sk-, gsk-, xoxb-, xoxp-.
  out = out.replace(/\b(sk|gsk|xoxb|xoxp)-[A-Za-z0-9_-]{8,}\b/gi, '<redacted-token>');
  // xAI / Grok API keys (xai-).
  out = out.replace(/\bxai-[A-Za-z0-9_-]{20,}\b/g, '<redacted-token>');
  // Google OAuth access tokens (ya29.).
  out = out.replace(/\bya29\.[A-Za-z0-9_-]{20,}\b/g, '<redacted-token>');
  // GitHub personal access tokens (ghp_) and refresh tokens (ghr_).
  out = out.replace(/\bghp_[A-Za-z0-9]{36}\b/g, '<redacted-token>');
  out = out.replace(/\bghr_[A-Za-z0-9]{36}\b/g, '<redacted-token>');
  return out;
}

/**
 * Redact values of any object key matching SENSITIVE_KEY_RE (Phase 5, DSP-07).
 * Operates non-recursively on the top-level keys of the provided object and
 * returns a new object with sensitive values replaced by '<redacted>'.
 *
 * @param {object} obj
 * @returns {object}
 */
function redactObjectKeys(obj) {
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return obj;
  const out = {};
  for (const [key, value] of Object.entries(obj)) {
    out[key] = SENSITIVE_KEY_RE.test(key) ? '<redacted>' : value;
  }
  return out;
}

function sanitizeField(value, depth = 0) {
  if (depth > 6) return '[truncated]';
  if (value == null) return value;
  if (value instanceof Error) return serializeError(value);
  if (typeof value === 'string') return redactString(value);
  if (typeof value === 'number' || typeof value === 'boolean') return value;
  if (Array.isArray(value)) return value.map((item) => sanitizeField(item, depth + 1));
  if (typeof value === 'object') {
    const out = {};
    for (const [key, entry] of Object.entries(value)) {
      if (SENSITIVE_KEY_RE.test(key) || /authorization|cookie/i.test(key)) {
        out[key] = '<redacted>';
      } else {
        out[key] = sanitizeField(entry, depth + 1);
      }
    }
    return out;
  }
  return inspect(value, { depth: 1, breakLength: 120 });
}

function writeLine(stream, payload) {
  try {
    stream.write(`${JSON.stringify(payload)}\n`);
  } catch (error) {
    const fallback = {
      level: 'error',
      msg: 'logger_write_failed',
      err: serializeError(error),
      payload_hint: typeof payload?.msg === 'string' ? payload.msg : 'unknown'
    };
    process.stderr.write(`${JSON.stringify(fallback)}\n`);
  }
}

function createLogger(options = {}) {
  const stream = options.stream || process.stderr;
  const level = normalizeLogLevel(options.level || process.env.LOG_LEVEL || 'info');
  const rootBindings = {
    service: options.service || 'runtime-hardening',
    ...sanitizeField(options.bindings || {})
  };

  function shouldLog(methodLevel) {
    return LEVEL_WEIGHT[methodLevel] >= LEVEL_WEIGHT[level] && level !== 'silent';
  }

  function emit(methodLevel, msg, fields) {
    if (!shouldLog(methodLevel)) return;
    writeLine(stream, {
      ts: new Date().toISOString(),
      level: methodLevel,
      msg: String(msg || ''),
      ...rootBindings,
      ...(fields ? sanitizeField(fields) : {})
    });
  }

  function child(extraBindings = {}) {
    return createLogger({
      stream,
      level,
      service: rootBindings.service,
      bindings: {
        ...rootBindings,
        ...extraBindings
      }
    });
  }

  return {
    level,
    child,
    trace: (msg, fields) => emit('trace', msg, fields),
    debug: (msg, fields) => emit('debug', msg, fields),
    info: (msg, fields) => emit('info', msg, fields),
    warn: (msg, fields) => emit('warn', msg, fields),
    error: (msg, fields) => emit('error', msg, fields),
    fatal: (msg, fields) => emit('fatal', msg, fields)
  };
}

const logger = createLogger();

export { createLogger, logger, normalizeLogLevel, redactObjectKeys, redactString, sanitizeField };
