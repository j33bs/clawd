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

function buildPromptAuditPayload({
  backend,
  model,
  messages,
  metadata
}) {
  const safeMessages = Array.isArray(messages) ? messages : [];
  const parts = {
    system: 0,
    instruction: 0,
    history: 0,
    state: 0,
    user: 0,
    scratch: 0
  };

  const userMessageLengths = [];
  safeMessages.forEach((message) => {
    if (!message || typeof message.content !== 'string') {
      return;
    }
    const length = message.content.length;
    const role = String(message.role || 'user').toLowerCase();

    if (role === 'system') {
      parts.system += length;
      return;
    }

    if (role === 'user') {
      parts.user += length;
      userMessageLengths.push(length);
      return;
    }

    if (role === 'tool' || role === 'function' || role === 'scratch') {
      parts.scratch += length;
      return;
    }

    parts.history += length;
  });

  if (userMessageLengths.length > 0) {
    parts.instruction = userMessageLengths[userMessageLengths.length - 1];
    parts.history += Math.max(0, parts.user - parts.instruction);
  }

  const stateValue = getMetadataField(metadata, ['stateSummary', 'state_summary', 'state']);
  parts.state = sizeOfValue(stateValue);

  const scratchValue = getMetadataField(metadata, ['scratch', 'trace', 'traceLog', 'trace_log']);
  parts.scratch += sizeOfValue(scratchValue);

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
    backend,
    model: model || null,
    approxChars: estimateMessagesChars(safeMessages),
    parts,
    hash: hashPromptAudit(hashInput)
  };
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
  const safeMetadata = metadata && typeof metadata === 'object' ? metadata : {};

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

    let outboundMessages = safeMessages;
    if (router.isLocalBackend(selectedBackend)) {
      const parts = splitContinuityParts(safeMessages);
      const stateSummary = continuityStateSummary(safeMetadata, safeTaskId);
      const continuityMessages = buildContinuityMessages({
        system: parts.system,
        instruction: parts.instruction,
        history: parts.history,
        stateSummary,
        tailTurnsMax: safeMetadata.tailTurnsMax || safeMetadata.tail_turns_max,
        budgets: {
          maxPromptChars: MAX_LOCAL_PROMPT_CHARS,
          maxStateSummaryChars: safeMetadata.maxStateSummaryChars || safeMetadata.max_state_summary_chars
        }
      });

      const originalChars = estimateMessagesChars(safeMessages);
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

    try {
      const selectedModel =
        safeMetadata.model ||
        safeMetadata.modelId ||
        safeMetadata.model_id ||
        provider.defaultModel ||
        provider.model ||
        null;
      try {
        const auditEntry = buildPromptAuditPayload({
          backend: selectedBackend,
          model: selectedModel,
          messages: outboundMessages,
          metadata: safeMetadata
        });
        appendAudit(auditEntry);
      } catch (auditError) {
        console.warn(`[prompt_audit] ${auditError.message}`);
      }

      const result = await provider.call({
        messages: outboundMessages,
        metadata: safeMetadata,
        allowNetwork: routePlan.allowNetwork
      });

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
