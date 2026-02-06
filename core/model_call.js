const { BACKENDS, ERROR_CODES } = require('./model_constants');
const { normalizeProviderError } = require('./normalize_error');
const { createModelRuntime } = require('./model_runtime');

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

    if (
      selectedBackend === BACKENDS.LOCAL_QWEN &&
      routePlan.preferredBackend !== BACKENDS.LOCAL_QWEN
    ) {
      await emitNotification({
        type: 'routing_notice',
        timestamp: timestampIso(),
        message:
          routePlan.allowNetwork === false
            ? 'Network-disabled mode forced LOCAL_QWEN routing.'
            : 'Remote Claude backends unavailable; using LOCAL_QWEN fallback.',
        task_id: safeTaskId,
        task_class: routePlan.taskClass,
        from_backend: routePlan.preferredBackend,
        to_backend: BACKENDS.LOCAL_QWEN,
        trigger_code: triggerCode || ERROR_CODES.UNKNOWN,
        network_used: false,
        metadata: {
          requires_claude: routePlan.requiresClaude
        }
      });
    }

    try {
      const result = await provider.call({
        messages: safeMessages,
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
