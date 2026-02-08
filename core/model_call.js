const path = require('path');
const { BACKENDS, ERROR_CODES } = require('./model_constants');
const { normalizeProviderError } = require('./normalize_error');
const { createModelRuntime } = require('./model_runtime');
const {
  MAX_LOCAL_PROMPT_CHARS,
  buildContinuityMessages,
  enforceBudget,
  estimateMessagesChars
} = require('./continuity_prompt');
const { appendAudit, hash: hashPromptAudit } = require('./prompt_audit');
const {
  DEFAULT_MAX_CONSTITUTION_CHARS,
  DEFAULT_CONSTITUTION_SOURCE_PATH,
  DEFAULT_SUPPORTING_SOURCE_PATHS,
  loadConstitutionSources,
  buildConstitutionBlock,
  buildConstitutionAuditRecord,
  appendConstitutionAudit
} = require('./constitution_instantiation');

const LOCAL_INTENT_ALLOWLIST = new Set([
  'route',
  'classify',
  'summarize',
  'draft_short',
  'status'
]);
const LOCAL_FALLBACK_TRIGGER_CODES = new Set([
  ERROR_CODES.RATE_LIMIT,
  ERROR_CODES.TIMEOUT,
  ERROR_CODES.NETWORK
]);
const LOCAL_HEURISTIC_MAX_TOKENS = 256;
const LOCAL_HEURISTIC_INPUT_LIMIT = 2000;
const MAX_SYSTEM_PROMPT_CHARS = 12000;
const MAX_HISTORY_CHARS = 8000;
const MAX_TOTAL_INPUT_CHARS = 20000;
const STRICT_MAX_SYSTEM_PROMPT_CHARS = 8000;
const STRICT_MAX_HISTORY_CHARS = 4000;
const CONTEXT_WINDOW_PRECHECK_RATIO = 0.9;
const CONTROLLED_PROMPT_BLOCK_MESSAGE =
  "Context trimmed to safe limits. Please send 'continue' to proceed.";
const CONTROLLED_CONSTITUTION_UNAVAILABLE_MESSAGE =
  'Constitution unavailable; refusing to run to preserve governance integrity.';
const UNTRUSTED_CONTEXT_PATTERNS = [
  /chain_trace\.jsonl/i,
  /gateway\.log/i,
  /all models failed/i,
  /errorCode=/i,
  /stack:/i
];
const CONTEXT_FIELD_MAP = {
  project: {
    source: ['projectContext', 'project_context', 'projectContextChars'],
    include: ['projectContextIncluded', 'project_context_included']
  },
  nonProject: {
    source: ['nonProjectContext', 'non_project_context', 'nonProjectContextChars'],
    include: ['nonProjectContextIncluded', 'non_project_context_included']
  }
};

function resolveIntent(metadata) {
  if (!metadata || typeof metadata !== 'object') {
    return null;
  }
  return (
    metadata.intent ||
    metadata.taskIntent ||
    metadata.task_intent ||
    metadata.intent_name ||
    null
  );
}

function resolveRequestedMaxTokens(metadata) {
  if (!metadata || typeof metadata !== 'object') {
    return null;
  }
  const value = metadata.maxTokens || metadata.max_tokens || null;
  const numeric = Number(value);
  return Number.isNaN(numeric) ? null : numeric;
}

function messageInputLength(messages = []) {
  return messages.reduce((sum, message) => {
    if (!message || typeof message.content !== 'string') {
      return sum;
    }
    return sum + message.content.length;
  }, 0);
}

function hasResearchFlags(metadata) {
  if (!metadata || typeof metadata !== 'object') {
    return false;
  }
  return Boolean(
    metadata.research ||
      metadata.requiresResearch ||
      metadata.longContext ||
      metadata.long_context ||
      metadata.deepResearch
  );
}

function allowLocalByHeuristic(metadata, messages) {
  const requestedMaxTokens = resolveRequestedMaxTokens(metadata);
  if (requestedMaxTokens && requestedMaxTokens > LOCAL_HEURISTIC_MAX_TOKENS) {
    return false;
  }
  if (messageInputLength(messages) > LOCAL_HEURISTIC_INPUT_LIMIT) {
    return false;
  }
  if (hasResearchFlags(metadata)) {
    return false;
  }
  return true;
}

function allowLocalForIntent(metadata, messages) {
  const intent = resolveIntent(metadata);
  if (intent) {
    return LOCAL_INTENT_ALLOWLIST.has(String(intent).toLowerCase());
  }
  return allowLocalByHeuristic(metadata, messages);
}

function allowLocalForTrigger(pendingTransition, allowNetwork) {
  if (allowNetwork === false) {
    return true;
  }
  if (!pendingTransition) {
    return false;
  }
  if (pendingTransition.reason === 'cooldown') {
    return true;
  }
  return LOCAL_FALLBACK_TRIGGER_CODES.has(pendingTransition.triggerCode);
}

function splitContinuityParts(messages = []) {
  const systemParts = [];
  const history = [];

  messages.forEach((message) => {
    if (!message || typeof message.content !== 'string') {
      return;
    }
    const role = String(message.role || 'user').toLowerCase();
    if (role === 'system') {
      systemParts.push(message.content);
      return;
    }
    if (role === 'assistant' || role === 'user') {
      history.push({ role, content: message.content });
    }
  });

  let instruction = null;
  for (let i = history.length - 1; i >= 0; i -= 1) {
    if (history[i].role === 'user') {
      instruction = history[i].content;
      history.splice(i, 1);
      break;
    }
  }

  return {
    system: systemParts.join('\n\n').trim(),
    instruction: instruction || '',
    history
  };
}

function sizeOfValue(value) {
  if (value == null) {
    return 0;
  }
  if (typeof value === 'string') {
    return value.length;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value).length;
  }
  try {
    return JSON.stringify(value).length;
  } catch (error) {
    return 0;
  }
}

function getMetadataField(metadata, keys = []) {
  if (!metadata || typeof metadata !== 'object') {
    return null;
  }
  for (const key of keys) {
    if (Object.prototype.hasOwnProperty.call(metadata, key)) {
      return metadata[key];
    }
  }
  return null;
}

function setMetadataField(metadata, keys = [], value) {
  if (!metadata || typeof metadata !== 'object') {
    return;
  }
  for (const key of keys) {
    if (!key) {
      continue;
    }
    metadata[key] = value;
  }
}

function containsUntrustedContext(value) {
  if (typeof value !== 'string') {
    return false;
  }
  return UNTRUSTED_CONTEXT_PATTERNS.some((pattern) => pattern.test(value));
}

function normalizeMessageRole(role) {
  const normalized = String(role || 'user').toLowerCase();
  if (
    normalized === 'system' ||
    normalized === 'assistant' ||
    normalized === 'user' ||
    normalized === 'tool' ||
    normalized === 'function' ||
    normalized === 'scratch'
  ) {
    return normalized;
  }
  return 'user';
}

function envFlagEnabled(name) {
  return String(process.env[name] || '')
    .trim()
    .toLowerCase() === '1';
}

function parseConstitutionSupportingPaths(value) {
  if (value == null || value === '') {
    return DEFAULT_SUPPORTING_SOURCE_PATHS;
  }

  const parsed = String(value)
    .split(path.delimiter)
    .map((entry) => entry.trim())
    .filter(Boolean);

  return parsed.length > 0 ? parsed : DEFAULT_SUPPORTING_SOURCE_PATHS;
}

function computePromptParts(messages = []) {
  const safeMessages = Array.isArray(messages) ? messages : [];
  let systemPrompt = 0;
  let history = 0;
  let userPrompt = 0;
  let historyCount = 0;
  let latestUserIndex = -1;
  const conversational = [];

  safeMessages.forEach((message) => {
    if (!message || typeof message.content !== 'string') {
      return;
    }
    const role = normalizeMessageRole(message.role);
    const contentLength = message.content.length;
    if (role === 'system') {
      systemPrompt += contentLength;
      return;
    }
    conversational.push({ role, contentLength });
    if (role === 'user') {
      latestUserIndex = conversational.length - 1;
    }
  });

  conversational.forEach((entry, index) => {
    if (index === latestUserIndex) {
      userPrompt += entry.contentLength;
      return;
    }
    history += entry.contentLength;
    historyCount += 1;
  });

  return {
    systemPrompt,
    userPrompt,
    history,
    historyCount
  };
}

function truncateWithMarker(text, maxChars, label) {
  const value = typeof text === 'string' ? text : '';
  const cap = Number(maxChars);
  if (!Number.isFinite(cap) || cap <= 0) {
    return {
      text: '',
      truncated: value.length > 0
    };
  }
  if (value.length <= cap) {
    return { text: value, truncated: false };
  }

  const removedChars = value.length - cap;
  const marker = `[TRUNCATED_${label}_HEAD:${removedChars} chars removed]\n`;
  const markerOnly = marker.length >= cap;
  const keepChars = markerOnly ? 0 : cap - marker.length;
  const suffix = keepChars > 0 ? value.slice(value.length - keepChars) : '';
  const truncatedText = markerOnly ? marker.slice(0, cap) : `${marker}${suffix}`;

  return {
    text: truncatedText,
    truncated: true
  };
}

function dropUntrustedMessages(messages = []) {
  const dropped = [];
  const sanitized = [];

  for (const message of messages) {
    if (!message || typeof message.content !== 'string') {
      continue;
    }
    const role = normalizeMessageRole(message.role);
    if (role !== 'user' && containsUntrustedContext(message.content)) {
      dropped.push(role);
      continue;
    }
    sanitized.push({
      role,
      content: message.content
    });
  }

  return {
    messages: sanitized,
    dropped
  };
}

function windowHistoryMessages(historyMessages = [], maxChars) {
  const cap = Number(maxChars);
  if (!Number.isFinite(cap) || cap <= 0) {
    return {
      messages: [],
      truncated: historyMessages.length > 0
    };
  }

  let remaining = cap;
  let truncated = false;
  const keptReverse = [];

  for (let i = historyMessages.length - 1; i >= 0; i -= 1) {
    const message = historyMessages[i];
    if (!message || typeof message.content !== 'string') {
      continue;
    }
    const length = message.content.length;

    if (remaining <= 0) {
      truncated = true;
      continue;
    }

    if (length <= remaining) {
      keptReverse.push({
        role: message.role,
        content: message.content
      });
      remaining -= length;
      continue;
    }

    const truncatedMessage = truncateWithMarker(message.content, remaining, 'HISTORY');
    if (truncatedMessage.text) {
      keptReverse.push({
        role: message.role,
        content: truncatedMessage.text
      });
    }
    remaining = 0;
    truncated = true;
  }

  const messages = keptReverse.reverse();
  if (messages.length < historyMessages.length) {
    truncated = true;
  }

  return {
    messages,
    truncated
  };
}

function buildBudgetedMessages(messages = [], caps = {}) {
  const maxSystemChars = Number(caps.maxSystemChars ?? MAX_SYSTEM_PROMPT_CHARS);
  const maxHistoryChars = Number(caps.maxHistoryChars ?? MAX_HISTORY_CHARS);
  const safeMessages = Array.isArray(messages) ? messages : [];

  const systemSegments = [];
  const conversation = [];
  let latestUserConversationIndex = -1;

  safeMessages.forEach((message) => {
    if (!message || typeof message.content !== 'string') {
      return;
    }
    const role = normalizeMessageRole(message.role);
    const content = message.content;
    if (role === 'system') {
      systemSegments.push(content);
      return;
    }
    conversation.push({
      role,
      content
    });
    if (role === 'user') {
      latestUserConversationIndex = conversation.length - 1;
    }
  });

  const userMessage =
    latestUserConversationIndex >= 0 ? conversation[latestUserConversationIndex] : null;
  const historyMessages = conversation.filter((_, index) => index !== latestUserConversationIndex);
  const windowedHistory = windowHistoryMessages(historyMessages, maxHistoryChars);
  const cappedSystem = truncateWithMarker(systemSegments.join('\n\n').trim(), maxSystemChars, 'SYSTEM');

  const assembled = [];
  if (cappedSystem.text) {
    assembled.push({
      role: 'system',
      content: cappedSystem.text
    });
  }
  windowedHistory.messages.forEach((message) => {
    assembled.push({
      role: message.role,
      content: message.content
    });
  });
  if (userMessage && typeof userMessage.content === 'string') {
    assembled.push({
      role: 'user',
      content: userMessage.content
    });
  }

  return {
    messages: assembled,
    parts: computePromptParts(assembled),
    totalChars: estimateMessagesChars(assembled),
    metadata: {
      historyDropped: windowedHistory.truncated,
      systemTightened: cappedSystem.truncated
    }
  };
}

function stripUntrustedMetadata(metadata = {}) {
  const next = metadata && typeof metadata === 'object' ? { ...metadata } : {};

  const projectContextSource = sizeOfValue(getMetadataField(next, CONTEXT_FIELD_MAP.project.source));
  const nonProjectContextSource = sizeOfValue(
    getMetadataField(next, CONTEXT_FIELD_MAP.nonProject.source)
  );
  const projectIncludedRaw = getMetadataField(next, CONTEXT_FIELD_MAP.project.include);
  const nonProjectIncludedRaw = getMetadataField(next, CONTEXT_FIELD_MAP.nonProject.include);

  let projectContextIncluded =
    typeof projectIncludedRaw === 'boolean' ? projectIncludedRaw : null;
  let nonProjectContextIncluded =
    typeof nonProjectIncludedRaw === 'boolean' ? nonProjectIncludedRaw : null;

  const projectContextValue = getMetadataField(next, CONTEXT_FIELD_MAP.project.source);
  const nonProjectContextValue = getMetadataField(next, CONTEXT_FIELD_MAP.nonProject.source);

  if (containsUntrustedContext(projectContextValue)) {
    setMetadataField(next, CONTEXT_FIELD_MAP.project.source, '');
    projectContextIncluded = false;
  }

  if (containsUntrustedContext(nonProjectContextValue)) {
    setMetadataField(next, CONTEXT_FIELD_MAP.nonProject.source, '');
    nonProjectContextIncluded = false;
  }

  const dropFields = [
    'untrustedContext',
    'untrusted_context',
    'trace',
    'traceLog',
    'trace_log',
    'gatewayLog',
    'gateway_log',
    'chainTrace',
    'chain_trace'
  ];

  dropFields.forEach((field) => {
    if (Object.prototype.hasOwnProperty.call(next, field)) {
      delete next[field];
    }
  });

  if (projectContextIncluded === false) {
    setMetadataField(next, CONTEXT_FIELD_MAP.project.include, false);
  }
  if (nonProjectContextIncluded === false) {
    setMetadataField(next, CONTEXT_FIELD_MAP.nonProject.include, false);
  }

  return {
    metadata: next,
    auditContext: {
      projectContextSource,
      nonProjectContextSource,
      projectContextIncluded,
      nonProjectContextIncluded,
      projectContextIncludedChars:
        projectContextIncluded === false ? 0 : projectContextSource,
      nonProjectContextIncludedChars:
        nonProjectContextIncluded === false ? 0 : nonProjectContextSource
    }
  };
}

function resolveContextWindow(provider, metadata) {
  const metadataWindow = Number(
    getMetadataField(metadata, ['contextWindow', 'context_window', 'modelContextWindow'])
  );
  if (Number.isFinite(metadataWindow) && metadataWindow > 0) {
    return metadataWindow;
  }

  const providerWindow = Number(provider && provider.contextWindow);
  if (Number.isFinite(providerWindow) && providerWindow > 0) {
    return providerWindow;
  }

  return null;
}

function enforcePromptBudget(messages = [], options = {}) {
  const maxSystemChars = Number(options.maxSystemChars ?? MAX_SYSTEM_PROMPT_CHARS);
  const maxHistoryChars = Number(options.maxHistoryChars ?? MAX_HISTORY_CHARS);
  const maxTotalChars = Number(options.maxTotalChars ?? MAX_TOTAL_INPUT_CHARS);
  const strictSystemChars = Number(
    options.strictSystemChars ?? STRICT_MAX_SYSTEM_PROMPT_CHARS
  );

  let built = buildBudgetedMessages(messages, {
    maxSystemChars,
    maxHistoryChars
  });
  let historyDropped = built.metadata.historyDropped;
  let systemTightened = built.metadata.systemTightened;

  if (built.totalChars > maxTotalChars && built.parts.history > 0) {
    const noHistory = buildBudgetedMessages(messages, {
      maxSystemChars,
      maxHistoryChars: 0
    });
    built = noHistory;
    historyDropped = true;
    systemTightened = systemTightened || noHistory.metadata.systemTightened;
  }

  if (built.totalChars > maxTotalChars) {
    const strictSystemOnly = buildBudgetedMessages(messages, {
      maxSystemChars: Math.min(maxSystemChars, strictSystemChars),
      maxHistoryChars: 0
    });
    built = strictSystemOnly;
    historyDropped = true;
    systemTightened = true;
  }

  const violation =
    built.parts.systemPrompt > maxSystemChars ||
    built.parts.history > maxHistoryChars ||
    built.totalChars > maxTotalChars;

  return {
    messages: built.messages,
    parts: built.parts,
    totalChars: built.totalChars,
    violation,
    historyDropped,
    systemTightened,
    caps: {
      maxSystemChars,
      maxHistoryChars,
      maxTotalChars
    }
  };
}

function buildPromptAuditPayload({
  phase,
  backend,
  model,
  messages,
  metadata,
  auditContext,
  attempt = null
}) {
  const safeMessages = Array.isArray(messages) ? messages : [];
  const parts = computePromptParts(safeMessages);
  const contextFromMetadata = {
    projectContextSource: sizeOfValue(getMetadataField(metadata, CONTEXT_FIELD_MAP.project.source)),
    nonProjectContextSource: sizeOfValue(
      getMetadataField(metadata, CONTEXT_FIELD_MAP.nonProject.source)
    ),
    projectContextIncluded: getMetadataField(metadata, CONTEXT_FIELD_MAP.project.include),
    nonProjectContextIncluded: getMetadataField(metadata, CONTEXT_FIELD_MAP.nonProject.include)
  };
  const context =
    auditContext && typeof auditContext === 'object'
      ? {
          ...contextFromMetadata,
          ...auditContext
        }
      : contextFromMetadata;
  const projectContextIncluded =
    typeof context.projectContextIncluded === 'boolean'
      ? context.projectContextIncluded
      : null;
  const nonProjectContextIncluded =
    typeof context.nonProjectContextIncluded === 'boolean'
      ? context.nonProjectContextIncluded
      : null;
  const projectContextSource = Number(context.projectContextSource || 0);
  const nonProjectContextSource = Number(context.nonProjectContextSource || 0);
  const projectContextIncludedChars =
    typeof context.projectContextIncludedChars === 'number'
      ? context.projectContextIncludedChars
      : projectContextIncluded === false
        ? 0
        : projectContextSource;
  const nonProjectContextIncludedChars =
    typeof context.nonProjectContextIncludedChars === 'number'
      ? context.nonProjectContextIncludedChars
      : nonProjectContextIncluded === false
        ? 0
        : nonProjectContextSource;
  const approxChars = parts.systemPrompt + parts.userPrompt + parts.history;

  const hashInput = safeMessages
    .map((message) => {
      if (!message || typeof message.content !== 'string') {
        return '';
      }
      return `${String(message.role || 'user')}:${message.content}`;
    })
    .join('\n---\n');

  return {
    ts: Date.now(),
    phase: phase || 'before_call',
    backend,
    model: model || null,
    approxChars,
    parts: {
      ...parts,
      projectContextSource,
      nonProjectContextSource,
      projectContextIncluded,
      nonProjectContextIncluded,
      projectContextIncludedChars,
      nonProjectContextIncludedChars
    },
    attempt,
    hash: hashPromptAudit(hashInput)
  };
}

function appendPromptAuditSafe(payload) {
  try {
    appendAudit(payload);
  } catch (auditError) {
    console.warn(`[prompt_audit] ${auditError.message}`);
  }
}

function appendConstitutionAuditSafe(payload) {
  try {
    appendConstitutionAudit(payload);
  } catch (auditError) {
    console.warn(`[constitution_audit] ${auditError.message}`);
  }
}

function continuityStateSummary(metadata, taskId) {
  if (metadata && typeof metadata === 'object') {
    const summary = metadata.stateSummary || metadata.state_summary || metadata.state;
    if (summary) {
      return String(summary);
    }
    const lane = metadata.lane || metadata.task_lane || metadata.session_lane;
    if (lane) {
      return `Task ${taskId} (lane=${lane})`;
    }
  }
  return `Task ${taskId}`;
}

function continuityOverflowError(error) {
  if (!error) {
    return false;
  }
  const message = String(error.message || '').toLowerCase();
  return (
    message.includes('context overflow') ||
    message.includes('prompt too large') ||
    message.includes('context length')
  );
}

function timestampIso() {
  return new Date().toISOString();
}

function generateTaskId() {
  return `task_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function backendFromCooldownKey(key) {
  if (key === 'oath') {
    return BACKENDS.OATH_CLAUDE;
  }
  if (key === 'anthropic') {
    return BACKENDS.ANTHROPIC_CLAUDE_API;
  }
  return 'UNKNOWN';
}

function isKnownErrorCode(value) {
  return Object.prototype.hasOwnProperty.call(ERROR_CODES, String(value || ''));
}

function getRuntime() {
  if (!global.__OPENCLAW_MODEL_RUNTIME) {
    global.__OPENCLAW_MODEL_RUNTIME = createModelRuntime();
  }
  return global.__OPENCLAW_MODEL_RUNTIME;
}

function getProvider(runtime, backend) {
  return runtime.providers ? runtime.providers[backend] : null;
}

async function callModel({
  taskId,
  messages,
  taskClass,
  requiresClaude,
  allowNetwork,
  preferredBackend,
  metadata
}) {
  const runtime = getRuntime();
  const router = runtime.router;
  const cooldownManager = runtime.cooldownManager;
  const logger = runtime.logger;
  const events = [];
  let budgetDiagnosticLogged = false;
  let continuityOverflowLogged = false;

  const safeTaskId = taskId || generateTaskId();
  const safeMessages = Array.isArray(messages) ? messages : [];
  const safeMetadata = metadata && typeof metadata === 'object' ? { ...metadata } : {};
  const constitutionEnforced = envFlagEnabled('OPENCLAW_CONSTITUTION_ENFORCE');
  const constitutionMaxChars = Number(process.env.OPENCLAW_CONSTITUTION_MAX_CHARS || DEFAULT_MAX_CONSTITUTION_CHARS);
  const constitutionSourcePath =
    process.env.OPENCLAW_CONSTITUTION_SOURCE_PATH || DEFAULT_CONSTITUTION_SOURCE_PATH;
  const constitutionSupportingPaths = parseConstitutionSupportingPaths(
    process.env.OPENCLAW_CONSTITUTION_SUPPORTING_PATHS
  );
  let constitutionSnapshot = null;
  let constitutionLoadError = null;

  try {
    constitutionSnapshot = loadConstitutionSources({
      sourcePath: constitutionSourcePath,
      supportingPaths: constitutionSupportingPaths,
      maxChars: Number.isFinite(constitutionMaxChars) ? constitutionMaxChars : DEFAULT_MAX_CONSTITUTION_CHARS
    });
    appendConstitutionAuditSafe(
      buildConstitutionAuditRecord({
        phase: 'constitution_instantiated',
        runId: safeTaskId,
        constitution: constitutionSnapshot
      })
    );
  } catch (error) {
    constitutionLoadError = error;
    appendConstitutionAuditSafe({
      ts: Date.now(),
      phase: 'constitution_instantiated',
      runId: safeTaskId,
      sha256: null,
      approxChars: 0,
      truncated: false,
      sourceCount: 0,
      sources: [],
      loadError: true,
      errorCode: error && error.code ? String(error.code) : 'CONSTITUTION_LOAD_FAILED'
    });
  }

  const routePlan = router.buildRoutePlan({
    taskClass,
    requiresClaude,
    allowNetwork,
    preferredBackend,
    metadata: safeMetadata,
    messages: safeMessages
  });

  async function emitFallbackEvent(entry) {
    events.push(entry);
    if (logger && typeof logger.logFallbackEvent === 'function') {
      await logger.logFallbackEvent(entry);
    }
  }

  async function emitNotification(entry) {
    events.push(entry);
    if (logger && typeof logger.logNotification === 'function') {
      await logger.logNotification(entry);
    }
  }

  async function emitLocalFallbackBlocked({ backend, intent, reason, pendingTransition }) {
    const fromBackend = pendingTransition ? pendingTransition.fromBackend : routePlan.preferredBackend;
    const triggerCode = pendingTransition ? pendingTransition.triggerCode : ERROR_CODES.UNKNOWN;

    await emitFallbackEvent({
      event_type: 'BACKEND_ERROR',
      task_id: safeTaskId,
      task_class: routePlan.taskClass,
      from_backend: fromBackend,
      to_backend: backend,
      trigger_code: triggerCode,
      provider_error_code: 'local_fallback_disallowed',
      network_used: router.networkUsedForBackend(backend),
      timestamp: timestampIso(),
      rationale: 'local_fallback_disallowed',
      metadata: {
        intent: intent || null,
        reason
      }
    });

    await emitNotification({
      type: 'routing_notice',
      timestamp: timestampIso(),
      message: `Local fallback disallowed for intent=${intent || 'unknown'} (reason=${reason}).`,
      task_id: safeTaskId,
      task_class: routePlan.taskClass,
      from_backend: fromBackend,
      to_backend: backend,
      trigger_code: triggerCode,
      network_used: router.networkUsedForBackend(backend),
      metadata: {
        requires_claude: routePlan.requiresClaude,
        intent: intent || null,
        reason
      }
    });

    const error = new Error(`Local fallback disallowed for intent=${intent || 'unknown'}`);
    error.code = 'LOCAL_FALLBACK_DISALLOWED';
    error.events = events;
    throw error;
  }

  async function emitCooldownClears() {
    if (!cooldownManager || typeof cooldownManager.clearExpired !== 'function') {
      return;
    }

    const clearEvents = cooldownManager.clearExpired(new Date());
    for (const clearEvent of clearEvents) {
      const backend = backendFromCooldownKey(clearEvent.backend_key);
      await emitFallbackEvent({
        event_type: 'COOLDOWN_CLEAR',
        task_id: safeTaskId,
        task_class: routePlan.taskClass,
        from_backend: backend,
        to_backend: backend,
        trigger_code: ERROR_CODES.NONE,
        provider_error_code: null,
        network_used: router.networkUsedForBackend(backend),
        timestamp: clearEvent.timestamp || timestampIso(),
        rationale: clearEvent.rationale || 'cooldown_expired',
        metadata: {
          backend_key: clearEvent.backend_key
        }
      });
    }
  }

  function healthTriggerCode(backend, health) {
    if (!health || health.ok !== false) {
      return ERROR_CODES.NONE;
    }

    if (health.reason === 'cooldown') {
      const key = router.cooldownKeyForBackend(backend);
      const state = key ? cooldownManager.getState(key) : null;
      return (state && state.lastError) || ERROR_CODES.UNKNOWN;
    }

    if (health.reason === 'missing_api_key') {
      return ERROR_CODES.AUTH;
    }

    if (isKnownErrorCode(health.reason)) {
      return String(health.reason).toUpperCase();
    }

    return ERROR_CODES.UNKNOWN;
  }

  function routeRationaleForSelection(fromBackend, toBackend, triggerCode, pendingReason) {
    if (pendingReason === 'cooldown') {
      return `${String(fromBackend).toLowerCase()}_on_cooldown_fallback`;
    }
    if (pendingReason === 'missing_api_key') {
      return 'anthropic_unavailable_missing_key_fallback';
    }
    if (triggerCode !== ERROR_CODES.NONE && triggerCode !== ERROR_CODES.UNKNOWN) {
      return `provider_error_fallback_${String(triggerCode).toLowerCase()}`;
    }
    if (routePlan.allowNetwork === false) {
      return 'network_disallowed_force_local';
    }
    if (fromBackend && fromBackend !== toBackend) {
      return 'preferred_backend_unavailable';
    }
    return 'route_selected';
  }

  async function emitRouteSelection(fromBackend, toBackend, triggerCode, providerErrorCode, pendingReason) {
    if (
      !fromBackend ||
      (fromBackend === toBackend &&
        toBackend === routePlan.preferredBackend &&
        triggerCode === ERROR_CODES.NONE)
    ) {
      return;
    }

    await emitFallbackEvent({
      event_type: 'ROUTE_SELECT',
      task_id: safeTaskId,
      task_class: routePlan.taskClass,
      from_backend: fromBackend,
      to_backend: toBackend,
      trigger_code: triggerCode || ERROR_CODES.NONE,
      provider_error_code: providerErrorCode || null,
      network_used: router.networkUsedForBackend(toBackend),
      timestamp: timestampIso(),
      rationale: routeRationaleForSelection(fromBackend, toBackend, triggerCode, pendingReason),
      metadata: {
        requires_claude: routePlan.requiresClaude
      }
    });
  }

  await emitCooldownClears();

  const candidates = Array.isArray(routePlan.candidates) ? routePlan.candidates : [];
  let pendingTransition = null;
  let lastError = null;
  let selectedBackend = null;

  for (const backend of candidates) {
    const provider = getProvider(runtime, backend);
    if (!provider) {
      pendingTransition = {
        fromBackend: backend,
        triggerCode: ERROR_CODES.UNKNOWN,
        providerErrorCode: 'provider_missing',
        reason: 'provider_missing'
      };
      continue;
    }

    if (router.isLocalBackend(backend)) {
      const intent = resolveIntent(safeMetadata);
      if (!allowLocalForIntent(safeMetadata, safeMessages)) {
        await emitLocalFallbackBlocked({
          backend,
          intent,
          reason: 'intent_not_allowed',
          pendingTransition
        });
      }
      if (!allowLocalForTrigger(pendingTransition, routePlan.allowNetwork)) {
        await emitLocalFallbackBlocked({
          backend,
          intent,
          reason: 'trigger_not_allowed',
          pendingTransition
        });
      }
    }

    let health = { ok: true };
    if (typeof provider.health === 'function') {
      try {
        health = await provider.health({ metadata: safeMetadata });
      } catch (healthError) {
        const normalizedHealthError = normalizeProviderError(healthError, backend);
        health = {
          ok: false,
          reason: normalizedHealthError.code,
          status: normalizedHealthError.status,
          rawCode: normalizedHealthError.rawCode
        };
      }
    }

    if (!health || health.ok === false) {
      const triggerCode = healthTriggerCode(backend, health);
      if (health && health.reason !== 'cooldown') {
        await emitFallbackEvent({
          event_type: 'BACKEND_ERROR',
          task_id: safeTaskId,
          task_class: routePlan.taskClass,
          from_backend: backend,
          to_backend: backend,
          trigger_code: triggerCode,
          provider_error_code: health && health.rawCode ? String(health.rawCode) : health && health.reason ? String(health.reason) : null,
          network_used: router.networkUsedForBackend(backend),
          timestamp: timestampIso(),
          rationale: 'provider_unhealthy',
          metadata: {
            reason: health && health.reason ? String(health.reason) : 'unhealthy',
            status: health && health.status ? health.status : null
          }
        });
      }

      pendingTransition = {
        fromBackend: backend,
        triggerCode,
        providerErrorCode: health && health.reason ? String(health.reason) : null,
        reason: health && health.reason ? String(health.reason) : 'unhealthy'
      };
      continue;
    }

    selectedBackend = backend;
    const fromBackend = pendingTransition ? pendingTransition.fromBackend : routePlan.preferredBackend;
    const triggerCode = pendingTransition ? pendingTransition.triggerCode : ERROR_CODES.NONE;
    const providerErrorCode = pendingTransition ? pendingTransition.providerErrorCode : null;
    const pendingReason = pendingTransition ? pendingTransition.reason : null;

    if (selectedBackend !== routePlan.preferredBackend || pendingTransition) {
      await emitRouteSelection(fromBackend, selectedBackend, triggerCode, providerErrorCode, pendingReason);
    }

    if (router.isLocalBackend(selectedBackend) && !router.isLocalBackend(routePlan.preferredBackend)) {
      await emitNotification({
        type: 'routing_notice',
        timestamp: timestampIso(),
        message:
          routePlan.allowNetwork === false
            ? `Network-disabled mode forced ${selectedBackend} routing.`
            : `Remote providers unavailable; using ${selectedBackend} fallback.`,
        task_id: safeTaskId,
        task_class: routePlan.taskClass,
        from_backend: routePlan.preferredBackend,
        to_backend: selectedBackend,
        trigger_code: triggerCode || ERROR_CODES.UNKNOWN,
        network_used: false,
        metadata: {
          requires_claude: routePlan.requiresClaude
        }
      });
    }

    const metadataSanitized = stripUntrustedMetadata(safeMetadata);
    let providerMetadata = metadataSanitized.metadata;
    let auditContext = metadataSanitized.auditContext;
    let outboundMessages = safeMessages;
    const droppedUntrusted = dropUntrustedMessages(outboundMessages);
    outboundMessages = droppedUntrusted.messages;

    if (constitutionEnforced) {
      if (constitutionLoadError || !constitutionSnapshot || !constitutionSnapshot.text) {
        appendConstitutionAuditSafe({
          ts: Date.now(),
          phase: 'constitution_enforced',
          runId: safeTaskId,
          sha256: constitutionSnapshot && constitutionSnapshot.sha256 ? constitutionSnapshot.sha256 : null,
          approxChars:
            constitutionSnapshot && typeof constitutionSnapshot.approxChars === 'number'
              ? constitutionSnapshot.approxChars
              : 0,
          truncated: Boolean(constitutionSnapshot && constitutionSnapshot.truncated),
          sourceCount:
            constitutionSnapshot && Array.isArray(constitutionSnapshot.sources)
              ? constitutionSnapshot.sources.length
              : 0,
          sources:
            constitutionSnapshot && Array.isArray(constitutionSnapshot.sources)
              ? constitutionSnapshot.sources
              : [],
          included: false,
          includedChars: 0,
          enforceActive: true,
          errorCode:
            constitutionLoadError && constitutionLoadError.code
              ? String(constitutionLoadError.code)
              : 'CONSTITUTION_LOAD_FAILED'
        });

        await emitFallbackEvent({
          event_type: 'BACKEND_ERROR',
          task_id: safeTaskId,
          task_class: routePlan.taskClass,
          from_backend: selectedBackend || backend,
          to_backend: selectedBackend || backend,
          trigger_code: ERROR_CODES.UNKNOWN,
          provider_error_code: 'constitution_unavailable',
          network_used: router.networkUsedForBackend(selectedBackend || backend),
          timestamp: timestampIso(),
          rationale: 'constitution_unavailable_blocked',
          metadata: {
            enforce_active: true
          }
        });

        return {
          backend: selectedBackend || backend,
          response: {
            text: CONTROLLED_CONSTITUTION_UNAVAILABLE_MESSAGE,
            raw: {
              controlled: true,
              reason: 'CONSTITUTION_UNAVAILABLE'
            }
          },
          usage: null,
          events
        };
      }

      const constitutionBlock = buildConstitutionBlock({
        text: constitutionSnapshot.text,
        sha256: constitutionSnapshot.sha256,
        truncated: constitutionSnapshot.truncated
      });
      outboundMessages = [{ role: 'system', content: constitutionBlock }, ...outboundMessages];

      appendConstitutionAuditSafe({
        ...buildConstitutionAuditRecord({
          phase: 'constitution_enforced',
          runId: safeTaskId,
          constitution: constitutionSnapshot
        }),
        included: true,
        includedChars: constitutionBlock.length,
        enforceActive: true
      });
    }

    if (router.isLocalBackend(selectedBackend)) {
      const parts = splitContinuityParts(outboundMessages);
      const stateSummary = continuityStateSummary(providerMetadata, safeTaskId);
      const continuityMessages = buildContinuityMessages({
        system: parts.system,
        instruction: parts.instruction,
        history: parts.history,
        stateSummary,
        tailTurnsMax: providerMetadata.tailTurnsMax || providerMetadata.tail_turns_max,
        budgets: {
          maxPromptChars: MAX_LOCAL_PROMPT_CHARS,
          maxStateSummaryChars:
            providerMetadata.maxStateSummaryChars || providerMetadata.max_state_summary_chars
        }
      });

      const originalChars = estimateMessagesChars(outboundMessages);
      const enforced = enforceBudget(continuityMessages, MAX_LOCAL_PROMPT_CHARS);
      outboundMessages = Array.isArray(enforced.value) ? enforced.value : continuityMessages;
      const finalChars = estimateMessagesChars(outboundMessages);
      const dropped = Math.max(0, originalChars - finalChars);

      if (!budgetDiagnosticLogged && (enforced.truncated || originalChars > finalChars)) {
        budgetDiagnosticLogged = true;
        await emitFallbackEvent({
          event_type: 'CONTINUITY_BUDGET',
          task_id: safeTaskId,
          task_class: routePlan.taskClass,
          from_backend: routePlan.preferredBackend,
          to_backend: selectedBackend,
          trigger_code: ERROR_CODES.NONE,
          provider_error_code: null,
          network_used: false,
          timestamp: timestampIso(),
          rationale: '[diagnostic] continuity_prompt budget applied',
          metadata: {
            originalChars,
            finalChars,
            dropped
          }
        });
      }

      if (finalChars > MAX_LOCAL_PROMPT_CHARS) {
        if (!budgetDiagnosticLogged) {
          budgetDiagnosticLogged = true;
          await emitFallbackEvent({
            event_type: 'CONTINUITY_BUDGET',
            task_id: safeTaskId,
            task_class: routePlan.taskClass,
            from_backend: routePlan.preferredBackend,
            to_backend: selectedBackend,
            trigger_code: ERROR_CODES.NONE,
            provider_error_code: 'budget_defensive_truncate',
            network_used: false,
            timestamp: timestampIso(),
            rationale: '[diagnostic] continuity_prompt budget applied',
            metadata: {
              originalChars,
              finalChars,
              dropped
            }
          });
        }
        const finalEnforced = enforceBudget(outboundMessages, MAX_LOCAL_PROMPT_CHARS);
        outboundMessages = Array.isArray(finalEnforced.value)
          ? finalEnforced.value
          : outboundMessages;
      }
    }

    let budgetedPrompt = enforcePromptBudget(outboundMessages, {
      maxSystemChars: MAX_SYSTEM_PROMPT_CHARS,
      maxHistoryChars: MAX_HISTORY_CHARS,
      maxTotalChars: MAX_TOTAL_INPUT_CHARS,
      strictSystemChars: STRICT_MAX_SYSTEM_PROMPT_CHARS
    });
    outboundMessages = budgetedPrompt.messages;

    const contextWindow = resolveContextWindow(provider, providerMetadata);
    const preflightLimit =
      contextWindow && contextWindow > 0
        ? Math.floor(contextWindow * CONTEXT_WINDOW_PRECHECK_RATIO)
        : null;
    let strictPassApplied = false;

    if (preflightLimit && budgetedPrompt.totalChars > preflightLimit) {
      strictPassApplied = true;
      budgetedPrompt = enforcePromptBudget(outboundMessages, {
        maxSystemChars: STRICT_MAX_SYSTEM_PROMPT_CHARS,
        maxHistoryChars: STRICT_MAX_HISTORY_CHARS,
        maxTotalChars: Math.min(MAX_TOTAL_INPUT_CHARS, preflightLimit),
        strictSystemChars: STRICT_MAX_SYSTEM_PROMPT_CHARS
      });
      outboundMessages = budgetedPrompt.messages;
    }

    const invariantViolation =
      budgetedPrompt.parts.systemPrompt > MAX_SYSTEM_PROMPT_CHARS ||
      budgetedPrompt.parts.history > MAX_HISTORY_CHARS ||
      budgetedPrompt.totalChars > MAX_TOTAL_INPUT_CHARS;
    const preflightViolation =
      preflightLimit != null && budgetedPrompt.totalChars > preflightLimit;
    const budgetBlocked =
      budgetedPrompt.violation || invariantViolation || Boolean(preflightViolation);

    if (droppedUntrusted.dropped.length > 0) {
      providerMetadata = {
        ...providerMetadata,
        nonProjectContextIncluded: false,
        non_project_context_included: false
      };
      auditContext = {
        ...auditContext,
        nonProjectContextIncluded: false,
        nonProjectContextIncludedChars: 0
      };
    }

    try {
      const selectedModel =
        providerMetadata.model ||
        providerMetadata.modelId ||
        providerMetadata.model_id ||
        provider.defaultModel ||
        provider.model ||
        null;
      appendPromptAuditSafe(
        buildPromptAuditPayload({
          phase: 'embedded_prompt_before',
          backend: selectedBackend,
          model: selectedModel,
          messages: outboundMessages,
          metadata: providerMetadata,
          auditContext,
          attempt: 'prepare'
        })
      );

      appendPromptAuditSafe(
        buildPromptAuditPayload({
          phase: 'before_call',
          backend: selectedBackend,
          model: selectedModel,
          messages: outboundMessages,
          metadata: providerMetadata,
          auditContext,
          attempt: 'provider_call'
        })
      );

      if (budgetBlocked) {
        await emitFallbackEvent({
          event_type: 'BACKEND_ERROR',
          task_id: safeTaskId,
          task_class: routePlan.taskClass,
          from_backend: selectedBackend,
          to_backend: selectedBackend,
          trigger_code: ERROR_CODES.CONTEXT,
          provider_error_code: 'prompt_budget_blocked',
          network_used: router.networkUsedForBackend(selectedBackend),
          timestamp: timestampIso(),
          rationale: 'prompt_budget_blocked',
          metadata: {
            context_window: contextWindow || null,
            preflight_limit: preflightLimit || null,
            strict_pass_applied: strictPassApplied,
            history_dropped: budgetedPrompt.historyDropped,
            system_tightened: budgetedPrompt.systemTightened,
            dropped_untrusted_roles: droppedUntrusted.dropped
          }
        });

        appendPromptAuditSafe(
          buildPromptAuditPayload({
            phase: 'embedded_attempt',
            backend: selectedBackend,
            model: selectedModel,
            messages: outboundMessages,
            metadata: providerMetadata,
            auditContext,
            attempt: 'blocked'
          })
        );

        return {
          backend: selectedBackend,
          response: {
            text: CONTROLLED_PROMPT_BLOCK_MESSAGE,
            raw: {
              controlled: true,
              reason: 'PROMPT_BUDGET_BLOCKED',
              contextWindow: contextWindow || null,
              preflightLimit: preflightLimit || null,
              strictPassApplied
            }
          },
          usage: null,
          events
        };
      }

      const result = await provider.call({
        messages: outboundMessages,
        metadata: providerMetadata,
        allowNetwork: routePlan.allowNetwork
      });

      appendPromptAuditSafe(
        buildPromptAuditPayload({
          phase: 'embedded_attempt',
          backend: selectedBackend,
          model: selectedModel,
          messages: outboundMessages,
          metadata: providerMetadata,
          auditContext,
          attempt: 'success'
        })
      );

      return {
        backend: selectedBackend,
        response: {
          text: result && typeof result.text === 'string' ? result.text : '',
          raw: result ? result.raw : null
        },
        usage: (result && result.usage) || null,
        events
      };
    } catch (error) {
      const selectedModel =
        providerMetadata.model ||
        providerMetadata.modelId ||
        providerMetadata.model_id ||
        provider.defaultModel ||
        provider.model ||
        null;
      appendPromptAuditSafe(
        buildPromptAuditPayload({
          phase: 'embedded_attempt',
          backend: selectedBackend || backend,
          model: selectedModel,
          messages: outboundMessages,
          metadata: providerMetadata,
          auditContext,
          attempt: 'error'
        })
      );

      if (router.isLocalBackend(backend) && continuityOverflowError(error)) {
        if (!continuityOverflowLogged) {
          continuityOverflowLogged = true;
          await emitFallbackEvent({
            event_type: 'BACKEND_ERROR',
            task_id: safeTaskId,
            task_class: routePlan.taskClass,
            from_backend: backend,
            to_backend: backend,
            trigger_code: ERROR_CODES.CONTEXT,
            provider_error_code: 'continuity_overflow',
            network_used: false,
            timestamp: timestampIso(),
            rationale: 'continuity_overflow',
            metadata: {
              provider: backend
            }
          });
        }

        const overflowError = new Error('Continuity overflow: prompt too large for local model');
        overflowError.code = 'CONTINUITY_OVERFLOW';
        overflowError.events = events;
        throw overflowError;
      }

      const normalized = normalizeProviderError(error, backend);
      lastError = error;

      await emitFallbackEvent({
        event_type: 'BACKEND_ERROR',
        task_id: safeTaskId,
        task_class: routePlan.taskClass,
        from_backend: backend,
        to_backend: backend,
        trigger_code: normalized.code || ERROR_CODES.UNKNOWN,
        provider_error_code: normalized.rawCode || (normalized.status ? String(normalized.status) : null),
        network_used: router.networkUsedForBackend(backend),
        timestamp: timestampIso(),
        rationale: 'provider_error',
        metadata: {
          provider: normalized.provider,
          status: normalized.status || null
        }
      });

      const cooldownKey = router.cooldownKeyForBackend(backend);
      if (cooldownKey && cooldownManager && typeof cooldownManager.recordError === 'function') {
        const cooldownUpdate = cooldownManager.recordError(cooldownKey, normalized.code, new Date());
        if (cooldownUpdate && cooldownUpdate.cooldownSet) {
          await emitFallbackEvent({
            event_type: 'COOLDOWN_SET',
            task_id: safeTaskId,
            task_class: routePlan.taskClass,
            from_backend: backend,
            to_backend: backend,
            trigger_code: normalized.code || ERROR_CODES.UNKNOWN,
            provider_error_code: normalized.rawCode || null,
            network_used: router.networkUsedForBackend(backend),
            timestamp: timestampIso(),
            rationale: 'cooldown_applied',
            metadata: {
              backend_key: cooldownKey,
              disabled_until: cooldownUpdate.state ? cooldownUpdate.state.disabledUntil : null,
              strike_count: cooldownUpdate.state ? cooldownUpdate.state.strikeCount : 0
            }
          });
        }
      }

      pendingTransition = {
        fromBackend: backend,
        triggerCode: normalized.code || ERROR_CODES.UNKNOWN,
        providerErrorCode: normalized.rawCode || null,
        reason: 'provider_error'
      };
      selectedBackend = null;
    }
  }

  const terminalError = lastError || new Error('No healthy model backend available');
  terminalError.code = terminalError.code || 'NO_BACKEND_AVAILABLE';
  terminalError.events = events;
  throw terminalError;
}

module.exports = {
  callModel
};
