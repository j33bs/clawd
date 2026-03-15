#!/usr/bin/env node
'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

function tryRequireOpenClawSdk() {
  try {
    // eslint-disable-next-line global-require
    return require('openclaw/plugin-sdk');
  } catch {
    return {};
  }
}

function resolveRepoRoot() {
  return path.resolve(__dirname, '..', '..');
}

function resolveStateDir(env = process.env) {
  if (typeof env.OPENCLAW_STATE_DIR === 'string' && env.OPENCLAW_STATE_DIR.trim()) {
    return path.resolve(env.OPENCLAW_STATE_DIR.trim());
  }
  if (typeof env.OPENCLAW_CONFIG_PATH === 'string' && env.OPENCLAW_CONFIG_PATH.trim()) {
    return path.dirname(path.resolve(env.OPENCLAW_CONFIG_PATH.trim()));
  }
  const cwdCandidate = path.join(process.cwd(), '.openclaw');
  if (fs.existsSync(cwdCandidate)) return cwdCandidate;
  return path.join(os.homedir(), '.openclaw');
}

function readJsonIfExists(filePath) {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch {
    return null;
  }
}

function readTextIfExists(filePath) {
  try {
    return fs.readFileSync(filePath, 'utf8');
  } catch {
    return '';
  }
}

function sha256(input) {
  return crypto.createHash('sha256').update(String(input), 'utf8').digest('hex');
}

function isTelegramContext(ctx) {
  const channel = String(ctx?.channelId || ctx?.messageProvider || '').trim().toLowerCase();
  return channel === 'telegram';
}

function loadSessionStore(env = process.env) {
  const stateDir = resolveStateDir(env);
  const storePath = path.join(stateDir, 'agents', 'main', 'sessions', 'sessions.json');
  return readJsonIfExists(storePath) || {};
}

function getSessionEntry(sessionKey, env = process.env) {
  if (!sessionKey) return null;
  const store = loadSessionStore(env);
  return store[sessionKey] || null;
}

function hasManualSessionOverride(sessionKey, env = process.env) {
  const entry = getSessionEntry(sessionKey, env);
  if (!entry || typeof entry !== 'object') return false;
  return Boolean(
    (typeof entry.providerOverride === 'string' && entry.providerOverride.trim()) ||
      (typeof entry.modelOverride === 'string' && entry.modelOverride.trim())
  );
}

function loadTelegramSurfacePolicy(repoRoot = resolveRepoRoot()) {
  const policyPath = path.join(repoRoot, 'workspace', 'policy', 'llm_policy.json');
  const policy = readJsonIfExists(policyPath) || {};
  const routing = policy.routing || {};
  const surface = (routing.surface_profiles || {}).telegram || {};
  const intents = surface.intents || {};
  const capabilityRouter = surface.capability_router || {};
  const conversationOrder = (intents.conversation || {}).order || [];
  const providerId =
    conversationOrder[0] ||
    capabilityRouter.planningProvider ||
    capabilityRouter.reasoningProvider ||
    capabilityRouter.codeProvider ||
    null;
  const provider = providerId ? (policy.providers || {})[providerId] || {} : {};
  const models = Array.isArray(provider.models) ? provider.models : [];
  const modelId = typeof models[0]?.id === 'string' ? models[0].id : null;
  return {
    policyPath,
    policyProfile: 'surface:telegram',
    providerId,
    modelId
  };
}

function buildSurfaceOverlay({ surface = 'telegram', includeMemory = true, mode = 'conversation' } = {}) {
  const normalizedSurface = String(surface || 'unknown').trim().toLowerCase() || 'unknown';
  const normalizedMode = String(mode || 'conversation').trim().toLowerCase() || 'conversation';
  const memoryMode = includeMemory ? 'memory:on' : 'memory:off';
  const overlayId = `surface:${normalizedSurface}|mode:${normalizedMode}|${memoryMode}`;
  const overlayText = [
    '## Active surface',
    '',
    `- surface: ${normalizedSurface}`,
    `- mode: ${normalizedMode}`,
    `- memory: ${includeMemory ? 'included' : 'excluded'}`,
    '- response goal: Codex-direct quality adapted to chat constraints',
    '- keep file/path references explicit when repo-grounded',
    '- make execution state and residual uncertainty concrete',
  ].join('\n');
  return { overlayId, overlayText };
}

function buildConversationKernelPacket(
  { surface = 'telegram', includeMemory = true, mode = 'conversation' } = {},
  repoRoot = resolveRepoRoot()
) {
  const kernelPath = path.join(repoRoot, 'nodes', 'c_lawd', 'CONVERSATION_KERNEL.md');
  const userPath = path.join(repoRoot, 'USER.md');
  const memoryPath = path.join(repoRoot, 'MEMORY.md');
  const parts = [];

  const kernelText = readTextIfExists(kernelPath).trim();
  if (kernelText) parts.push(kernelText);

  const userText = readTextIfExists(userPath).trim();
  if (userText) parts.push(`## USER profile\n\n${userText}`);

  if (includeMemory) {
    const memoryText = readTextIfExists(memoryPath).trim();
    if (memoryText) parts.push(`## MEMORY\n\n${memoryText}`);
  }

  const { overlayId, overlayText } = buildSurfaceOverlay({ surface, includeMemory, mode });
  parts.push(overlayText);
  const promptText = parts.filter(Boolean).join('\n\n').trim();

  return {
    kernelId: `c_lawd:${overlayId}`,
    kernelHash: promptText ? sha256(promptText) : null,
    surfaceOverlay: overlayId,
    promptText,
    kernelPath,
    userPath,
    memoryPath
  };
}

function appendJsonl(filePath, record) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.appendFileSync(filePath, `${JSON.stringify(record)}\n`, 'utf8');
}

function routeLogPath(repoRoot = resolveRepoRoot()) {
  return path.join(repoRoot, 'workspace', 'audit', 'telegram_route_provenance.jsonl');
}

function buildTelegramLlmOutputRecord(event, ctx, env = process.env) {
  if (!isTelegramContext(ctx)) return null;
  const repoRoot = resolveRepoRoot();
  const route = loadTelegramSurfacePolicy(repoRoot);
  const kernel = buildConversationKernelPacket({ surface: 'telegram', includeMemory: true, mode: 'conversation' }, repoRoot);
  const entry = getSessionEntry(ctx?.sessionKey, env) || {};
  return {
    ts: new Date().toISOString(),
    phase: 'llm_output',
    channel: 'telegram',
    session_key: ctx?.sessionKey || null,
    session_id: ctx?.sessionId || event?.sessionId || null,
    run_id: event?.runId || null,
    delivery_to: entry?.deliveryContext?.to || null,
    account_id: entry?.deliveryContext?.accountId || null,
    provider: event?.provider || entry?.modelProvider || null,
    model: event?.model || entry?.model || null,
    message_provider: ctx?.messageProvider || null,
    route_source: 'telegram_surface_router_plugin',
    policy_profile: route.policyProfile,
    repo_policy_path: route.policyPath,
    repo_provider_id: route.providerId,
    repo_model_id: route.modelId,
    kernel_id: kernel.kernelId,
    kernel_hash: kernel.kernelHash,
    surface_overlay: kernel.surfaceOverlay,
    system_prompt_provider: entry?.systemPromptReport?.provider || null,
    system_prompt_model: entry?.systemPromptReport?.model || null
  };
}

function resolveTelegramRuntimeOverride(ctx, env = process.env) {
  if (!isTelegramContext(ctx)) return null;
  if (ctx?.sessionKey && hasManualSessionOverride(ctx.sessionKey, env)) {
    return null;
  }
  const route = loadTelegramSurfacePolicy(resolveRepoRoot());
  if (!route.providerId || !route.modelId) return null;
  return {
    providerOverride: 'openai-codex',
    modelOverride: route.modelId,
    route
  };
}

function buildTelegramPromptInjection(ctx) {
  if (!isTelegramContext(ctx)) return null;
  const kernel = buildConversationKernelPacket({ surface: 'telegram', includeMemory: true, mode: 'conversation' }, resolveRepoRoot());
  if (!kernel.promptText) return null;
  return {
    prependSystemContext: `${kernel.promptText}\n`
  };
}

const { emptyPluginConfigSchema } = tryRequireOpenClawSdk();

const plugin = {
  id: 'openclaw_surface_router_plugin',
  name: 'Telegram Surface Router',
  description: 'Align Telegram turns with the repo Telegram surface policy and c_lawd kernel.',
  kind: 'tooling',
  configSchema: typeof emptyPluginConfigSchema === 'function' ? emptyPluginConfigSchema() : undefined,
  register(api) {
    api.on('gateway_start', (_event, ctx) => {
      api.logger.info('telegram_surface_router_plugin_active', {
        port: ctx?.port || null,
        policy_profile: 'surface:telegram'
      });
    });

    api.on('before_model_resolve', (_event, ctx) => {
      const override = resolveTelegramRuntimeOverride(ctx);
      if (!override) return;
      api.logger.info('telegram_surface_router_selected', {
        session_key: ctx?.sessionKey || null,
        channel_id: ctx?.channelId || null,
        provider: override.providerOverride,
        model: override.modelOverride,
        policy_profile: override.route.policyProfile,
        repo_provider_id: override.route.providerId
      });
      return {
        providerOverride: override.providerOverride,
        modelOverride: override.modelOverride
      };
    });

    api.on('before_prompt_build', (_event, ctx) => {
      const result = buildTelegramPromptInjection(ctx);
      if (!result) return;
      return result;
    });

    api.on('llm_output', (event, ctx) => {
      const record = buildTelegramLlmOutputRecord(event, ctx);
      if (!record) return;
      appendJsonl(routeLogPath(resolveRepoRoot()), record);
      api.logger.info('telegram_route_provenance_logged', {
        session_key: record.session_key,
        provider: record.provider,
        model: record.model,
        run_id: record.run_id,
        phase: record.phase
      });
    });
  }
};

module.exports = plugin;
module.exports.default = plugin;
module.exports._test = {
  buildConversationKernelPacket,
  buildSurfaceOverlay,
  buildTelegramLlmOutputRecord,
  buildTelegramPromptInjection,
  hasManualSessionOverride,
  loadTelegramSurfacePolicy,
  resolveRepoRoot,
  resolveStateDir,
  resolveTelegramRuntimeOverride
};
