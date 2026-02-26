import { logger } from '../log.mjs';

const DEFAULT_LIMITS = Object.freeze({
  maxPayloadBytes: 32 * 1024,
  maxKeys: 128,
  maxDepth: 8,
  maxStringLength: 4096,
  maxArrayLength: 256,
  maxNameLength: 128
});

function isPlainObject(value) {
  if (!value || typeof value !== 'object') return false;
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}

function createValidationError(reason, details = {}) {
  const error = new Error(`tool payload rejected: ${reason}`);
  error.code = 'TOOL_PAYLOAD_REJECTED';
  error.reason = reason;
  error.details = details;
  return error;
}

function safeByteLength(value) {
  try {
    return Buffer.byteLength(JSON.stringify(value), 'utf8');
  } catch {
    throw createValidationError('payload is not JSON-serializable');
  }
}

function validateName(name, limits) {
  if (typeof name !== 'string' || !name.trim()) {
    throw createValidationError('name must be a non-empty string');
  }
  if (name.length > limits.maxNameLength) {
    throw createValidationError('name too long', { maxNameLength: limits.maxNameLength });
  }
  if (!/^[a-zA-Z0-9_.:-]+$/.test(name)) {
    throw createValidationError('name has invalid characters');
  }
  return name.trim();
}

function walkValue(value, context) {
  if (context.depth > context.limits.maxDepth) {
    throw createValidationError('payload nesting too deep', { maxDepth: context.limits.maxDepth });
  }

  if (value == null || typeof value === 'boolean' || typeof value === 'number') return;

  if (typeof value === 'string') {
    if (value.length > context.limits.maxStringLength) {
      throw createValidationError('payload string too long', {
        maxStringLength: context.limits.maxStringLength
      });
    }
    return;
  }

  if (Array.isArray(value)) {
    if (value.length > context.limits.maxArrayLength) {
      throw createValidationError('payload array too long', {
        maxArrayLength: context.limits.maxArrayLength
      });
    }
    for (const entry of value) {
      walkValue(entry, {
        ...context,
        depth: context.depth + 1
      });
    }
    return;
  }

  if (!isPlainObject(value)) {
    throw createValidationError('payload contains non-plain object');
  }

  const entries = Object.entries(value);
  context.keyCount += entries.length;
  if (context.keyCount > context.limits.maxKeys) {
    throw createValidationError('payload has too many keys', {
      maxKeys: context.limits.maxKeys
    });
  }

  for (const [key, entry] of entries) {
    if (key.length > context.limits.maxNameLength) {
      throw createValidationError('payload key too long', {
        maxNameLength: context.limits.maxNameLength
      });
    }
    walkValue(entry, {
      ...context,
      depth: context.depth + 1
    });
  }
}

function summarizePayload(payload) {
  if (!payload || typeof payload !== 'object') return { kind: typeof payload };
  return {
    name: typeof payload.name === 'string' ? payload.name : '<unknown>',
    keys: isPlainObject(payload.args) ? Object.keys(payload.args).length : 0,
    bytes: safeByteLength(payload)
  };
}

function sanitizeToolInvocation(payload, options = {}) {
  const limits = {
    ...DEFAULT_LIMITS,
    ...(options.limits || {})
  };

  if (!isPlainObject(payload)) {
    throw createValidationError('payload must be an object');
  }

  const name = validateName(payload.name, limits);

  if (!isPlainObject(payload.args)) {
    throw createValidationError('args must be a plain object');
  }

  const sizeBytes = safeByteLength(payload);
  if (sizeBytes > limits.maxPayloadBytes) {
    throw createValidationError('payload too large', {
      maxPayloadBytes: limits.maxPayloadBytes,
      payloadBytes: sizeBytes
    });
  }

  walkValue(payload.args, {
    limits,
    depth: 0,
    keyCount: 0
  });

  return {
    name,
    args: payload.args
  };
}

function sanitizeToolInvocationOrThrow(payload, options = {}) {
  try {
    return sanitizeToolInvocation(payload, options);
  } catch (error) {
    const log = options.logger || logger;
    log.warn('tool_payload_rejected', {
      summary: summarizePayload(payload),
      reason: error.reason || error.message
    });
    throw error;
  }
}

export { DEFAULT_LIMITS, createValidationError, sanitizeToolInvocation, sanitizeToolInvocationOrThrow };
