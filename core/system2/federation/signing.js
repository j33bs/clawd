'use strict';

const { stableStringify } = require('../canonical_json');

class SigningDisabledError extends Error {
  constructor(message) {
    super(message || 'signing disabled');
    this.name = 'SigningDisabledError';
    this.code = 'SIGNING_DISABLED';
  }
}

class InsecureSigningNotAllowedError extends Error {
  constructor(message) {
    super(message || 'insecure signing not allowed');
    this.name = 'InsecureSigningNotAllowedError';
    this.code = 'INSECURE_SIGNING_NOT_ALLOWED';
  }
}

/**
 * Interface contract:
 * signer.sign(canonicalBytes, { keyId, alg }) -> { alg, key_id, sig }
 * verifier.verify(canonicalBytes, signature) -> boolean
 *
 * This module provides only the contract + safe stubs for Phase 2.
 */

function canonicalizeForSigning(envelope) {
  return Buffer.from(stableStringify(envelope), 'utf8');
}

function createInsecureNoneSigner(options = {}) {
  const allow = options.allowInsecureNone === true;
  return {
    sign: async function signNone() {
      if (!allow) throw new InsecureSigningNotAllowedError('alg=none requires explicit allowInsecureNone');
      return { alg: 'none', key_id: 'insecure_none', sig: 'stub' };
    }
  };
}

async function signEnvelope(envelope, signer, options = {}) {
  if (!options.enabled) throw new SigningDisabledError('signEnvelope requires options.enabled === true');
  if (!signer || typeof signer.sign !== 'function') {
    const err = new Error('signer missing');
    err.code = 'SIGNER_MISSING';
    throw err;
  }
  const bytes = canonicalizeForSigning(envelope);
  return signer.sign(bytes, { alg: options.alg, keyId: options.keyId });
}

async function verifyEnvelope(envelope, verifier, signature, options = {}) {
  if (!options.enabled) throw new SigningDisabledError('verifyEnvelope requires options.enabled === true');
  if (!verifier || typeof verifier.verify !== 'function') {
    const err = new Error('verifier missing');
    err.code = 'VERIFIER_MISSING';
    throw err;
  }
  const bytes = canonicalizeForSigning(envelope);
  return verifier.verify(bytes, signature);
}

module.exports = {
  SigningDisabledError,
  InsecureSigningNotAllowedError,
  canonicalizeForSigning,
  createInsecureNoneSigner,
  signEnvelope,
  verifyEnvelope
};

