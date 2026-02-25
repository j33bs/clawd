import {
  getConfig,
  redactConfigForLogs,
  logger,
  ensureWorkspaceDirectories,
  SessionManager,
  McpServerSingleflight,
  assertPathWithinRoot,
  sanitizeToolInvocationOrThrow,
  retryWithBackoff,
  sanitizeTelegramOutboundPayload
} from './hardening/index.mjs';

const GLOBAL_KEY = '__openclaw_runtime_hardening';
const TELEGRAM_FETCH_PATCH_KEY = '__openclaw_telegram_outbound_fetch_patch_installed';

function isTelegramSendEndpoint(url) {
  const raw = String(url || '');
  return /api\.telegram\.org/i.test(raw) && /\/(sendMessage|editMessageText|sendPhoto|sendVideo|sendDocument|sendAnimation|sendAudio|sendVoice)\b/.test(raw);
}

function hasSanitizableText(payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return false;
  return typeof payload.text === 'string' || typeof payload.caption === 'string';
}

function rewriteTelegramJsonBody(bodyText, runtimeLogger) {
  try {
    const parsed = JSON.parse(bodyText);
    if (!hasSanitizableText(parsed)) return { changed: false, body: bodyText };
    const { payload, changed } = sanitizeTelegramOutboundPayload(parsed, { logger: runtimeLogger });
    if (!changed) return { changed: false, body: bodyText };
    return { changed: true, body: JSON.stringify(payload) };
  } catch {
    return { changed: false, body: bodyText };
  }
}

function rewriteTelegramUrlEncodedBody(bodyText, runtimeLogger) {
  try {
    const params = new URLSearchParams(bodyText);
    if (!params.has('text') && !params.has('caption')) return { changed: false, body: bodyText };
    const record = Object.fromEntries(params.entries());
    const { payload, changed } = sanitizeTelegramOutboundPayload(record, { logger: runtimeLogger });
    if (!changed) return { changed: false, body: bodyText };

    for (const [key, value] of Object.entries(payload)) {
      if (typeof value === 'string') params.set(key, value);
    }
    return { changed: true, body: params.toString() };
  } catch {
    return { changed: false, body: bodyText };
  }
}

function rewriteTelegramFetchBody(body, runtimeLogger) {
  if (typeof body === 'string') {
    const trimmed = body.trim();
    if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
      return rewriteTelegramJsonBody(body, runtimeLogger);
    }
    return rewriteTelegramUrlEncodedBody(body, runtimeLogger);
  }

  if (body instanceof URLSearchParams) {
    const record = Object.fromEntries(body.entries());
    if (!hasSanitizableText(record)) return { changed: false, body };
    const { payload, changed } = sanitizeTelegramOutboundPayload(record, { logger: runtimeLogger });
    if (!changed) return { changed: false, body };
    const nextParams = new URLSearchParams(body);
    for (const [key, value] of Object.entries(payload)) {
      if (typeof value === 'string') nextParams.set(key, value);
    }
    return { changed: true, body: nextParams };
  }

  return { changed: false, body };
}

function installTelegramOutboundFetchSanitizer(runtimeLogger) {
  if (globalThis[TELEGRAM_FETCH_PATCH_KEY]) return;
  const originalFetch = globalThis.fetch;
  if (typeof originalFetch !== 'function') return;

  globalThis.fetch = async function patchedFetch(input, init) {
    const requestUrl = typeof input === 'string' ? input : input?.url;
    if (!isTelegramSendEndpoint(requestUrl)) {
      return originalFetch.call(this, input, init);
    }

    try {
      if (init && Object.hasOwn(init, 'body')) {
        const rewritten = rewriteTelegramFetchBody(init.body, runtimeLogger);
        if (rewritten.changed) {
          return originalFetch.call(this, input, { ...init, body: rewritten.body });
        }
        return originalFetch.call(this, input, init);
      }

      if (input && typeof input === 'object' && typeof input.clone === 'function') {
        const request = input;
        const clone = request.clone();
        const bodyText = await clone.text();
        if (bodyText) {
          const rewritten = rewriteTelegramFetchBody(bodyText, runtimeLogger);
          if (rewritten.changed) {
            const patched = new Request(request.url, {
              method: request.method,
              headers: request.headers,
              body: rewritten.body,
              redirect: request.redirect,
              signal: request.signal
            });
            return originalFetch.call(this, patched);
          }
        }
      }
    } catch (error) {
      runtimeLogger.warn('telegram_outbound_sanitize_patch_failed', { error });
    }

    return originalFetch.call(this, input, init);
  };

  globalThis[TELEGRAM_FETCH_PATCH_KEY] = true;
  runtimeLogger.info('telegram_outbound_fetch_sanitizer_installed');
}

if (!globalThis[GLOBAL_KEY]) {
  const config = getConfig();
  ensureWorkspaceDirectories(config);

  const runtimeLogger = logger.child({ module: 'runtime-hardening-overlay' });
  const sessionManager = new SessionManager({ config, logger: runtimeLogger });
  installTelegramOutboundFetchSanitizer(runtimeLogger);

  globalThis[GLOBAL_KEY] = {
    config,
    sessionManager,
    createMcpSingleflight(startServer) {
      return new McpServerSingleflight({
        config,
        logger: runtimeLogger,
        startServer
      });
    },
    assertPathWithinWorkspace(targetPath) {
      return assertPathWithinRoot(config.workspaceRoot, targetPath, {
        allowOutsideWorkspace: config.fsAllowOutsideWorkspace
      });
    },
    sanitizeToolInvocation(payload) {
      return sanitizeToolInvocationOrThrow(payload, { logger: runtimeLogger });
    },
    retryWithBackoff(task, options) {
      return retryWithBackoff(task, {
        logger: runtimeLogger,
        ...options
      });
    }
  };

  runtimeLogger.info('runtime_hardening_initialized', {
    config: redactConfigForLogs(config)
  });
}

export const runtimeHardening = globalThis[GLOBAL_KEY];
