import {
  getConfig,
  redactConfigForLogs,
  logger,
  installNetworkInterfacesGuard,
  ensureWorkspaceDirectories,
  SessionManager,
  McpServerSingleflight,
  assertPathWithinRoot,
  sanitizeToolInvocationOrThrow,
  retryWithBackoff,
  sanitizeOutboundPayload,
  buildTelegramSendPayload
} from './hardening/index.mjs';

const GLOBAL_KEY = '__openclaw_runtime_hardening';
const OUTBOUND_FETCH_PATCH_KEY = '__openclaw_outbound_fetch_patch_installed';

function classifyOutboundChannel(url) {
  const raw = String(url || '');
  if (
    /api\.telegram\.org/i.test(raw) &&
    /\/(sendMessage|editMessageText|sendPhoto|sendVideo|sendDocument|sendAnimation|sendAudio|sendVoice|sendMediaGroup|sendPoll)\b/i.test(
      raw
    )
  ) {
    return 'telegram';
  }
  if (/discord(?:app)?\.com/i.test(raw) && /\/api\/v\d+\/(webhooks|channels\/\d+\/messages)\b/i.test(raw)) {
    return 'discord';
  }
  if (/slack\.com/i.test(raw) && /\/api\/chat\.(postMessage|update)\b/i.test(raw)) {
    return 'slack';
  }
  if (/mattermost/i.test(raw) && /\/api\/v4\/posts\b/i.test(raw)) {
    return 'mattermost';
  }
  if (/(outlook\.office\.com|office\.com|teams\.microsoft\.com)/i.test(raw) && /(webhook|\/v1\/messages)\b/i.test(raw)) {
    return 'msteams';
  }
  return null;
}

function stringifyValue(value) {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (value == null) return '';
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function payloadShallowChanged(before, after) {
  const beforeKeys = Object.keys(before || {}).sort();
  const afterKeys = Object.keys(after || {}).sort();
  if (beforeKeys.length !== afterKeys.length) return true;
  for (let idx = 0; idx < beforeKeys.length; idx += 1) {
    if (beforeKeys[idx] !== afterKeys[idx]) return true;
    if (!Object.is(before[beforeKeys[idx]], after[beforeKeys[idx]])) return true;
  }
  return false;
}

function applyOutboundPolicy(payload, context) {
  const sanitized = sanitizeOutboundPayload(payload, {
    channel: context.channel,
    logger: context.logger
  });
  let nextPayload = sanitized.payload;
  let changed = sanitized.changed;
  let wantsReply = false;

  if (context.channel === 'telegram') {
    const hadReplyFields =
      Object.hasOwn(nextPayload, 'reply_to_message_id') ||
      Object.hasOwn(nextPayload, 'reply_parameters') ||
      Object.hasOwn(nextPayload, 'replyToMessageId');
    const modeApplied = buildTelegramSendPayload({
      payload: nextPayload,
      mode: context.config.telegramReplyMode
    });
    nextPayload = modeApplied.payload;
    wantsReply = modeApplied.wantsReply;
    if (payloadShallowChanged(sanitized.payload, nextPayload)) {
      changed = true;
    }
    if (hadReplyFields && !modeApplied.wantsReply) {
      context.logger.info('telegram_reply_mode_applied', {
        channel: 'telegram',
        mode: context.config.telegramReplyMode,
        correlation_id: sanitized.meta.correlation_id,
        chat_id: sanitized.meta.chat_id,
        message_id: sanitized.meta.message_id
      });
    }
  }

  return {
    payload: nextPayload,
    changed,
    wantsReply
  };
}

function rewriteOutboundJsonBody(bodyText, context) {
  try {
    const parsed = JSON.parse(bodyText);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return { changed: false, body: bodyText };
    }
    const rewritten = applyOutboundPolicy(parsed, context);
    if (!rewritten.changed) return { changed: false, body: bodyText };
    return { changed: true, body: JSON.stringify(rewritten.payload) };
  } catch {
    return { changed: false, body: bodyText };
  }
}

function rewriteOutboundUrlEncodedBody(bodyText, context) {
  try {
    const params = new URLSearchParams(bodyText);
    const record = Object.fromEntries(params.entries());
    const rewritten = applyOutboundPolicy(record, context);
    if (!rewritten.changed) return { changed: false, body: bodyText };
    const nextParams = new URLSearchParams();
    for (const [key, value] of Object.entries(rewritten.payload)) {
      if (value == null) continue;
      nextParams.set(key, stringifyValue(value));
    }
    return { changed: true, body: nextParams.toString() };
  } catch {
    return { changed: false, body: bodyText };
  }
}

function rewriteOutboundFormDataBody(form, context) {
  try {
    const stringValues = {};
    for (const [key, value] of form.entries()) {
      if (typeof value === 'string') stringValues[key] = value;
    }
    const rewritten = applyOutboundPolicy(stringValues, context);
    if (!rewritten.changed) return { changed: false, body: form };
    const flatValues = {};
    for (const [key, value] of Object.entries(rewritten.payload)) {
      if (value == null) continue;
      flatValues[key] = stringifyValue(value);
    }

    const next = new FormData();
    const seen = new Set();
    for (const [key, value] of form.entries()) {
      if (typeof value === 'string') {
        if (!Object.hasOwn(flatValues, key)) continue;
        next.append(key, flatValues[key]);
        seen.add(key);
        continue;
      }
      next.append(key, value);
      seen.add(key);
    }
    for (const [key, value] of Object.entries(flatValues)) {
      if (seen.has(key)) continue;
      next.append(key, value);
    }
    return { changed: true, body: next };
  } catch {
    return { changed: false, body: form };
  }
}

function rewriteOutboundFetchBody(body, context) {
  if (typeof body === 'string') {
    const trimmed = body.trim();
    if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
      return rewriteOutboundJsonBody(body, context);
    }
    return rewriteOutboundUrlEncodedBody(body, context);
  }
  if (body instanceof URLSearchParams) {
    return rewriteOutboundUrlEncodedBody(body.toString(), context);
  }
  if (typeof FormData !== 'undefined' && body instanceof FormData) {
    return rewriteOutboundFormDataBody(body, context);
  }
  return { changed: false, body };
}

function cloneRequestWithBody(request, body) {
  return new Request(request.url, {
    method: request.method,
    headers: request.headers,
    body,
    redirect: request.redirect,
    signal: request.signal
  });
}

function installOutboundFetchSanitizer(runtimeLogger, config) {
  if (globalThis[OUTBOUND_FETCH_PATCH_KEY]) return;
  const originalFetch = globalThis.fetch;
  if (typeof originalFetch !== 'function') return;

  globalThis.fetch = async function patchedFetch(input, init) {
    const requestUrl = typeof input === 'string' ? input : input?.url;
    const channel = classifyOutboundChannel(requestUrl);
    if (!channel) {
      return originalFetch.call(this, input, init);
    }

    const context = {
      channel,
      logger: runtimeLogger,
      config
    };

    try {
      if (init && Object.hasOwn(init, 'body')) {
        const rewritten = rewriteOutboundFetchBody(init.body, context);
        if (rewritten.changed) {
          return originalFetch.call(this, input, { ...init, body: rewritten.body });
        }
        return originalFetch.call(this, input, init);
      }

      if (input && typeof input === 'object' && typeof input.clone === 'function') {
        const request = input;
        const clone = request.clone();
        const contentType = String(clone.headers?.get?.('content-type') || '').toLowerCase();
        if (contentType.includes('application/json') || contentType.includes('application/x-www-form-urlencoded')) {
          const bodyText = await clone.text();
          const rewritten = rewriteOutboundFetchBody(bodyText, context);
          if (rewritten.changed) {
            return originalFetch.call(this, cloneRequestWithBody(request, rewritten.body));
          }
        } else if (contentType.includes('multipart/form-data') && typeof clone.formData === 'function') {
          const form = await clone.formData();
          const rewritten = rewriteOutboundFetchBody(form, context);
          if (rewritten.changed) {
            return originalFetch.call(this, cloneRequestWithBody(request, rewritten.body));
          }
        }
      }
    } catch (error) {
      runtimeLogger.warn('outbound_sanitize_patch_failed', { channel, error });
    }

    return originalFetch.call(this, input, init);
  };

  globalThis[OUTBOUND_FETCH_PATCH_KEY] = true;
  runtimeLogger.info('outbound_fetch_sanitizer_installed');
}

if (!globalThis[GLOBAL_KEY]) {
  const runtimeLogger = logger.child({ module: 'runtime-hardening-overlay' });
  installNetworkInterfacesGuard({ logger: runtimeLogger, processLike: process });

  const isStatusCommand = Array.isArray(process.argv) && process.argv.includes('status');
  let config = null;
  try {
    config = getConfig();
    ensureWorkspaceDirectories(config);
  } catch (error) {
    if (!isStatusCommand) throw error;
    runtimeLogger.warn('runtime_hardening_config_degraded_for_status', { error });
    try {
      const details = error && typeof error.message === 'string' ? error.message : String(error);
      process.stderr.write(`RUNTIME_HARDENING_CONFIG_DEGRADED: ${details}\n`);
    } catch {
      // ignore stderr write failures
    }
  }

  const sessionManager = config ? new SessionManager({ config, logger: runtimeLogger }) : null;
  if (config) {
    installOutboundFetchSanitizer(runtimeLogger, config);
  }

  function requireConfig() {
    if (config) return config;
    throw new Error('runtime hardening config is unavailable in status degraded mode');
  }

  globalThis[GLOBAL_KEY] = {
    config,
    sessionManager,
    createMcpSingleflight(startServer) {
      const readyConfig = requireConfig();
      return new McpServerSingleflight({
        config: readyConfig,
        logger: runtimeLogger,
        startServer
      });
    },
    assertPathWithinWorkspace(targetPath) {
      const readyConfig = requireConfig();
      return assertPathWithinRoot(readyConfig.workspaceRoot, targetPath, {
        allowOutsideWorkspace: readyConfig.fsAllowOutsideWorkspace
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
    config: config ? redactConfigForLogs(config) : { degraded_for_status: true }
  });
}

export const runtimeHardening = globalThis[GLOBAL_KEY];
