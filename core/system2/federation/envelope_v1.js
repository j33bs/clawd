'use strict';

function validateFederatedEnvelopeV1(obj) {
  const errors = [];
  function req(cond, msg) {
    if (!cond) errors.push(msg);
  }

  req(obj && typeof obj === 'object', 'envelope must be object');
  req(obj.type === 'federated_envelope_v1', 'type must be federated_envelope_v1');
  req(obj.version === '1', 'version must be 1');
  req(typeof obj.id === 'string' && obj.id.length > 0, 'id must be non-empty string');
  req(typeof obj.ts_utc === 'string' && obj.ts_utc.includes('T'), 'ts_utc must be ISO-like string');

  req(obj.routing && typeof obj.routing === 'object', 'routing must be object');
  if (obj.routing) {
    req(typeof obj.routing.from === 'string' && obj.routing.from.length > 0, 'routing.from required');
    req(typeof obj.routing.to === 'string' && obj.routing.to.length > 0, 'routing.to required');
    req(typeof obj.routing.topic === 'string' && obj.routing.topic.length > 0, 'routing.topic required');
    if (obj.routing.ttl_ms !== undefined) {
      req(Number.isFinite(obj.routing.ttl_ms), 'routing.ttl_ms must be number if present');
    }
  }

  req(obj.signature && typeof obj.signature === 'object', 'signature must be object');
  if (obj.signature) {
    req(typeof obj.signature.alg === 'string', 'signature.alg must be string');
    req(typeof obj.signature.key_id === 'string', 'signature.key_id must be string');
    req(typeof obj.signature.sig === 'string', 'signature.sig must be string');
  }

  req(obj.redaction && typeof obj.redaction === 'object', 'redaction must be object');
  if (obj.redaction) {
    req(typeof obj.redaction.applied === 'boolean', 'redaction.applied must be boolean');
    req(typeof obj.redaction.rules_version === 'string' && obj.redaction.rules_version.length > 0, 'redaction.rules_version required');
  }

  req(obj.payload !== undefined, 'payload required');

  return { ok: errors.length === 0, errors };
}

module.exports = {
  validateFederatedEnvelopeV1
};

