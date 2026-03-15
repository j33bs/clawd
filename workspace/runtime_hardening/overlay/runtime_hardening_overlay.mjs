import {
  getConfig,
  redactConfigForLogs,
  logger,
  installNetworkInterfacesGuard,
  checkVllmHealth,
  probePortOwner,
  buildUnknownPortHint,
  ensureWorkspaceDirectories,
  SessionManager,
  McpServerSingleflight,
  assertPathWithinRoot,
  sanitizeToolInvocationOrThrow,
  retryWithBackoff,
  sanitizeOutboundPayload,
  buildTelegramSendPayload,
  applySourceUiTaskDirectiveToText,
  auditTelegramRouteProvenance
} from '../src/index.mjs';
import { installHttpIngressContractSignal } from '../src/http_ingress_contract_signal.mjs';

const GLOBAL_KEY = '__openclaw_runtime_hardening';
const OUTBOUND_FETCH_PATCH_KEY = '__openclaw_outbound_fetch_patch_installed';
let cachedConfig;

export function getConfigOnce(env = process.env) {
  if (!cachedConfig) {
    cachedConfig = getConfig(env);
  }
  return cachedConfig;
}

function normalizeGatewayChannel(value) {
  const raw = String(value || '')
    .trim()
    .toLowerCase();
  if (!raw) return null;
  if (raw === 'team_chat') return 'teamchat';
  if (raw === 'teams' || raw === 'ms_teams' || raw === 'microsoft_teams') return 'msteams';
  if (raw === 'matter-most') return 'mattermost';
  if (raw === 'telegram' || raw === 'discord' || raw === 'slack' || raw === 'mattermost' || raw === 'msteams' || raw === 'teamchat') {
    return raw;
  }
  return 'generic';
}

function isGatewayToolMessageUrl(url) {
  return /\/api\/tool\/message\b/i.test(String(url || ''));
}

function extractGatewayChannelFromStringBody(bodyText) {
  if (typeof bodyText !== 'string') return null;
  const trimmed = bodyText.trim();
  if (!trimmed) return null;
  if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
    try {
      const parsed = JSON.parse(trimmed);
      return normalizeGatewayChannel(parsed?.channel);
    } catch {
      return null;
    }
  }
  try {
    const params = new URLSearchParams(bodyText);
    return normalizeGatewayChannel(params.get('channel'));
  } catch {
    return null;
  }
}

function extractGatewayChannelFromBody(body) {
  if (typeof body === 'string') return extractGatewayChannelFromStringBody(body);
  if (body instanceof URLSearchParams) return normalizeGatewayChannel(body.get('channel'));
  if (typeof FormData !== 'undefined' && body instanceof FormData) return normalizeGatewayChannel(body.get('channel'));
  return null;
}

function extractTelegramResponseMessageId(payload) {
  if (!payload || typeof payload !== 'object') return null;
  const messageId = payload?.result?.message_id;
  if (typeof messageId === 'number' || typeof messageId === 'string') return String(messageId);
  return null;
}

async function extractTelegramResponseMessageIdFromResponse(response) {
  try {
    const clone = response.clone();
    const contentType = String(clone.headers?.get?.('content-type') || '').toLowerCase();
    if (!contentType.includes('application/json')) return null;
    const payload = await clone.json();
    return extractTelegramResponseMessageId(payload);
  } catch {
    return null;
  }
}

function extractTelegramChatIdFromPayload(payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return null;
  const value = payload.chat_id ?? payload.chatId;
  if (value == null) return null;
  const raw = String(value).trim();
  return raw || null;
}

function classifyOutboundChannel(url, payloadChannel = null) {
  const raw = String(url || '');
  if (isGatewayToolMessageUrl(raw)) {
    return payloadChannel || 'generic';
  }
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

async function applyTelegramQueuePolicy(payload, context) {
  if (context.channel !== 'telegram' || !payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return { payload, changed: false };
  }

  let nextPayload = payload;
  let changed = false;
  for (const field of ['text', 'caption', 'message']) {
    if (typeof nextPayload[field] !== 'string') continue;
    const result = await applySourceUiTaskDirectiveToText({
      text: nextPayload[field],
      fetchImpl: globalThis.fetch,
      tasksUrl: context.config.sourceUiTasksUrl
    });
    if (!result.changed) continue;
    nextPayload = {
      ...nextPayload,
      [field]: result.text
    };
    changed = true;
    if (result.queued && result.receipt) {
      context.logger.info('source_ui_task_queued', {
        channel: context.channel,
        field,
        task_id: result.receipt.id,
        task_title: result.receipt.title,
        task_status: result.receipt.status
      });
    } else if (result.error) {
      context.logger.warn('source_ui_task_queue_failed', {
        channel: context.channel,
        field,
        error: result.error.message
      });
    } else {
      context.logger.warn('source_ui_unverified_queue_claim_downgraded', {
        channel: context.channel,
        field
      });
    }
  }

  return { payload: nextPayload, changed };
}

async function rewriteOutboundJsonBody(bodyText, context) {
  try {
    const parsed = JSON.parse(bodyText);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return { changed: false, body: bodyText };
    }
    const rewritten = applyOutboundPolicy(parsed, context);
    const queueAdjusted = await applyTelegramQueuePolicy(rewritten.payload, context);
    if (!rewritten.changed && !queueAdjusted.changed) return { changed: false, body: bodyText };
    return { changed: true, body: JSON.stringify(queueAdjusted.payload) };
  } catch {
    return { changed: false, body: bodyText };
  }
}

async function rewriteOutboundUrlEncodedBody(bodyText, context) {
  try {
    const params = new URLSearchParams(bodyText);
    const record = Object.fromEntries(params.entries());
    const rewritten = applyOutboundPolicy(record, context);
    const queueAdjusted = await applyTelegramQueuePolicy(rewritten.payload, context);
    if (!rewritten.changed && !queueAdjusted.changed) return { changed: false, body: bodyText };
    const nextParams = new URLSearchParams();
    for (const [key, value] of Object.entries(queueAdjusted.payload)) {
      if (value == null) continue;
      nextParams.set(key, stringifyValue(value));
    }
    return { changed: true, body: nextParams.toString() };
  } catch {
    return { changed: false, body: bodyText };
  }
}

async function rewriteOutboundFormDataBody(form, context) {
  try {
    const stringValues = {};
    for (const [key, value] of form.entries()) {
      if (typeof value === 'string') stringValues[key] = value;
    }
    const rewritten = applyOutboundPolicy(stringValues, context);
    const queueAdjusted = await applyTelegramQueuePolicy(rewritten.payload, context);
    if (!rewritten.changed && !queueAdjusted.changed) return { changed: false, body: form };
    const flatValues = {};
    for (const [key, value] of Object.entries(queueAdjusted.payload)) {
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

async function rewriteOutboundFetchBody(body, context) {
  if (typeof body === 'string') {
    const trimmed = body.trim();
    if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
      return await rewriteOutboundJsonBody(body, context);
    }
    return await rewriteOutboundUrlEncodedBody(body, context);
  }
  if (body instanceof URLSearchParams) {
    return await rewriteOutboundUrlEncodedBody(body.toString(), context);
  }
  if (typeof FormData !== 'undefined' && body instanceof FormData) {
    return await rewriteOutboundFormDataBody(body, context);
  }
  return { changed: false, body };
}

async function readNormalizedPayloadBody(body) {
  if (typeof body === 'string') {
    const trimmed = body.trim();
    if (!trimmed) return null;
    if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
      try {
        return JSON.parse(trimmed);
      } catch {
        return null;
      }
    }
    try {
      return Object.fromEntries(new URLSearchParams(body).entries());
    } catch {
      return null;
    }
  }
  if (body instanceof URLSearchParams) {
    return Object.fromEntries(body.entries());
  }
  if (typeof FormData !== 'undefined' && body instanceof FormData) {
    const out = {};
    for (const [key, value] of body.entries()) {
      if (typeof value === 'string') out[key] = value;
    }
    return out;
  }
  return null;
}

async function auditTelegramRouteForSend({ requestUrl, requestBody, response, context }) {
  if (!/api\.telegram\.org/i.test(String(requestUrl || ''))) return;
  const requestPayload = await readNormalizedPayloadBody(requestBody);
  const chatId = extractTelegramChatIdFromPayload(requestPayload);
  if (!chatId) return;
  const responseMessageId = await extractTelegramResponseMessageIdFromResponse(response);
  const record = auditTelegramRouteProvenance({
    chatId,
    responseMessageId,
    workspaceRoot: context.config.workspaceRoot,
    logPath: context.config.telegramRouteProvenanceLogPath
  });
  if (!record) return;
  context.logger.info('telegram_route_provenance_recorded', {
    chat_id: record.chat_id,
    response_message_id: record.response_message_id,
    session_key: record.session_key,
    provider: record.provider,
    model: record.model,
    api: record.api,
    route_source: record.route_source
  });
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

async function extractGatewayChannelFromRequestInput(input) {
  if (!input || typeof input !== 'object' || typeof input.clone !== 'function') return null;
  try {
    const clone = input.clone();
    const contentType = String(clone.headers?.get?.('content-type') || '').toLowerCase();
    if (contentType.includes('application/json') || contentType.includes('application/x-www-form-urlencoded')) {
      const bodyText = await clone.text();
      return extractGatewayChannelFromStringBody(bodyText);
    }
    if (contentType.includes('multipart/form-data') && typeof clone.formData === 'function') {
      const form = await clone.formData();
      return normalizeGatewayChannel(form.get('channel'));
    }
  } catch {
    return null;
  }
  return null;
}

function installOutboundFetchSanitizer(runtimeLogger, config) {
  if (globalThis[OUTBOUND_FETCH_PATCH_KEY]) return;
  const originalFetch = globalThis.fetch;
  if (typeof originalFetch !== 'function') return;

  globalThis.fetch = async function patchedFetch(input, init) {
    const requestUrl = typeof input === 'string' ? input : input?.url;
    let gatewayChannel = null;
    if (isGatewayToolMessageUrl(requestUrl)) {
      if (init && Object.hasOwn(init, 'body')) {
        gatewayChannel = extractGatewayChannelFromBody(init.body);
      } else {
        gatewayChannel = await extractGatewayChannelFromRequestInput(input);
      }
    }
    const channel = classifyOutboundChannel(requestUrl, gatewayChannel);
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
        const rewritten = await rewriteOutboundFetchBody(init.body, context);
        const requestBody = rewritten.changed ? rewritten.body : init.body;
        if (rewritten.changed) {
          const response = await originalFetch.call(this, input, { ...init, body: rewritten.body });
          if (channel === 'telegram') {
            await auditTelegramRouteForSend({ requestUrl, requestBody, response, context });
          }
          return response;
        }
        const response = await originalFetch.call(this, input, init);
        if (channel === 'telegram') {
          await auditTelegramRouteForSend({ requestUrl, requestBody, response, context });
        }
        return response;
      }

      if (input && typeof input === 'object' && typeof input.clone === 'function') {
        const request = input;
        const clone = request.clone();
        const contentType = String(clone.headers?.get?.('content-type') || '').toLowerCase();
        if (contentType.includes('application/json') || contentType.includes('application/x-www-form-urlencoded')) {
          const bodyText = await clone.text();
          const rewritten = await rewriteOutboundFetchBody(bodyText, context);
          if (rewritten.changed) {
            const response = await originalFetch.call(this, cloneRequestWithBody(request, rewritten.body));
            if (channel === 'telegram') {
              await auditTelegramRouteForSend({ requestUrl, requestBody: rewritten.body, response, context });
            }
            return response;
          }
          const response = await originalFetch.call(this, input, init);
          if (channel === 'telegram') {
            await auditTelegramRouteForSend({ requestUrl, requestBody: bodyText, response, context });
          }
          return response;
        } else if (contentType.includes('multipart/form-data') && typeof clone.formData === 'function') {
          const form = await clone.formData();
          const rewritten = await rewriteOutboundFetchBody(form, context);
          if (rewritten.changed) {
            const response = await originalFetch.call(this, cloneRequestWithBody(request, rewritten.body));
            if (channel === 'telegram') {
              await auditTelegramRouteForSend({ requestUrl, requestBody: rewritten.body, response, context });
            }
            return response;
          }
          const response = await originalFetch.call(this, input, init);
          if (channel === 'telegram') {
            await auditTelegramRouteForSend({ requestUrl, requestBody: form, response, context });
          }
          return response;
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
  installHttpIngressContractSignal({ logger: runtimeLogger });

  const isStatusCommand = Array.isArray(process.argv) && process.argv.includes('status');
  const isDashboardCommand = Array.isArray(process.argv) && process.argv.includes('dashboard');
  const allowlistRaw = typeof process.env.OPENCLAW_PROVIDER_ALLOWLIST === 'string' ? process.env.OPENCLAW_PROVIDER_ALLOWLIST : '';
  if (isDashboardCommand && !allowlistRaw.trim()) {
    process.env.OPENCLAW_PROVIDER_ALLOWLIST = 'local_vllm';
    runtimeLogger.info('dashboard_allowlist_defaulted', { openclawProviderAllowlist: 'local_vllm' });
  }
  if (isStatusCommand) {
    try {
      const vllmHealthy = await checkVllmHealth({ port: 8001, timeoutMs: 1200 });
      const probe = probePortOwner(8001);
      const hint = buildUnknownPortHint({ vllmHealthy, probe, port: 8001 });
      if (hint) {
        process.stderr.write(`${hint}\n`);
        runtimeLogger.warn('status_hint_vllm_port_held_unknown', {
          port: 8001,
          pid: probe.pid ?? null,
          cmd: probe.cmd ?? null
        });
      }
    } catch (error) {
      runtimeLogger.warn('status_hint_probe_failed', { error });
    }
  }

  let config = null;
  try {
    config = getConfigOnce();
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
    if (isDashboardCommand && !config.anthropicEnabled && Object.hasOwn(process.env, 'ANTHROPIC_API_KEY')) {
      delete process.env.ANTHROPIC_API_KEY;
      runtimeLogger.info('dashboard_env_sanitized', { removedEnv: 'ANTHROPIC_API_KEY' });
    }
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
