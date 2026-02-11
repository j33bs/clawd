'use strict';

const crypto = require('node:crypto');

const ENVELOPE_VERSION = 'v0';
const DEFAULT_KEY_ENV = 'SYSTEM2_ENVELOPE_HMAC_KEY';

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

function signEnvelopePayload(payload, signingKey) {
  const canonical = JSON.stringify(canonicalize(payload));
  return crypto.createHmac('sha256', signingKey).update(canonical).digest('hex');
}

function resolveSigningKey(options = {}) {
  const keyEnv = options.keyEnv || DEFAULT_KEY_ENV;
  return options.signingKey || process.env[keyEnv] || null;
}

function buildEnvelopePayload(payload, policyRecord, budgets, artifacts, options = {}) {
  return {
    envelope_version: ENVELOPE_VERSION,
    job_id: options.jobId || crypto.randomUUID(),
    requester_identity: options.requesterIdentity || 'system2',
    policy_decision_record: policyRecord || {},
    budgets: budgets || {},
    artifacts_manifest: artifacts || [],
    stream: {
      supported: true
    },
    cancel: {
      supported: true
    },
    payload: payload || {},
    created_at: options.createdAt || new Date().toISOString()
  };
}

function createSignedEnvelope(payload, policyRecord, budgets, artifacts, options = {}) {
  const signingKey = resolveSigningKey(options);
  if (!signingKey) {
    throw new Error('Missing envelope signing key');
  }

  const envelope = buildEnvelopePayload(payload, policyRecord, budgets, artifacts, options);
  envelope.signature = signEnvelopePayload(envelope, signingKey);
  return envelope;
}

function verifyEnvelope(envelope, options = {}) {
  const errors = [];

  if (!envelope || typeof envelope !== 'object') {
    return { ok: false, errors: ['envelope must be object'] };
  }

  const required = [
    'envelope_version',
    'job_id',
    'requester_identity',
    'policy_decision_record',
    'budgets',
    'artifacts_manifest',
    'payload',
    'created_at',
    'signature'
  ];
  required.forEach((field) => {
    if (!(field in envelope)) {
      errors.push(`missing field: ${field}`);
    }
  });

  if (envelope.envelope_version !== ENVELOPE_VERSION) {
    errors.push(`unsupported envelope_version: ${envelope.envelope_version}`);
  }

  const signingKey = resolveSigningKey(options);
  if (!signingKey) {
    errors.push('missing signing key');
  } else if (typeof envelope.signature === 'string' && envelope.signature.length > 0) {
    const copy = { ...envelope };
    const provided = copy.signature;
    delete copy.signature;
    const actual = signEnvelopePayload(copy, signingKey);
    if (provided !== actual) {
      errors.push('signature mismatch');
    }
  }

  return {
    ok: errors.length === 0,
    errors
  };
}

module.exports = {
  ENVELOPE_VERSION,
  DEFAULT_KEY_ENV,
  canonicalize,
  signEnvelopePayload,
  createSignedEnvelope,
  verifyEnvelope
};
