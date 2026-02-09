'use strict';

const crypto = require('node:crypto');

const REQUIRED_EVENT_FIELDS = ['ts', 'eventType', 'runId', 'git', 'host', 'config', 'payload', 'hash'];

function canonicalize(value) {
  if (Array.isArray(value)) {
    return value.map((item) => canonicalize(item));
  }

  if (value && typeof value === 'object') {
    const out = {};
    for (const key of Object.keys(value).sort()) {
      out[key] = canonicalize(value[key]);
    }
    return out;
  }

  return value;
}

function sha256Hex(input) {
  return crypto.createHash('sha256').update(input).digest('hex');
}

function computeEventHash(event) {
  const copy = { ...event };
  delete copy.hash;
  const canonical = JSON.stringify(canonicalize(copy));
  return sha256Hex(canonical);
}

function validateEventShape(event) {
  const errors = [];

  for (const field of REQUIRED_EVENT_FIELDS) {
    if (!(field in event)) {
      errors.push(`missing field: ${field}`);
    }
  }

  if (typeof event.ts !== 'number') {
    errors.push('ts must be number epoch ms');
  }

  if (typeof event.eventType !== 'string' || event.eventType.length === 0) {
    errors.push('eventType must be non-empty string');
  }

  if (typeof event.runId !== 'string' || event.runId.length === 0) {
    errors.push('runId must be non-empty string');
  }

  for (const objField of ['git', 'host', 'config', 'payload']) {
    if (!event[objField] || typeof event[objField] !== 'object' || Array.isArray(event[objField])) {
      errors.push(`${objField} must be object`);
    }
  }

  if (typeof event.hash !== 'string' || event.hash.length === 0) {
    errors.push('hash must be non-empty string');
  }

  return {
    ok: errors.length === 0,
    errors
  };
}

function createAuditEvent({ ts = Date.now(), eventType, runId, git, host, config, payload }) {
  const event = {
    ts,
    eventType,
    runId,
    git,
    host,
    config,
    payload,
    hash: ''
  };
  event.hash = computeEventHash(event);
  return event;
}

module.exports = {
  REQUIRED_EVENT_FIELDS,
  canonicalize,
  computeEventHash,
  createAuditEvent,
  validateEventShape
};
