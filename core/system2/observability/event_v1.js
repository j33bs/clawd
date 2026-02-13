'use strict';

function validateSystem2EventV1(obj) {
  const errors = [];
  function req(cond, msg) {
    if (!cond) errors.push(msg);
  }

  req(obj && typeof obj === 'object', 'event must be object');
  req(obj.type === 'system2_event_v1', 'type must be system2_event_v1');
  req(obj.version === '1', 'version must be 1');
  req(typeof obj.ts_utc === 'string' && obj.ts_utc.includes('T'), 'ts_utc must be ISO-like string');
  req(typeof obj.event_type === 'string' && obj.event_type.length > 0, 'event_type required');
  req(['debug', 'info', 'warn', 'error'].includes(obj.level), 'level must be one of debug|info|warn|error');
  req(obj.payload && typeof obj.payload === 'object', 'payload must be object');
  req(obj.context && typeof obj.context === 'object', 'context must be object');

  return { ok: errors.length === 0, errors };
}

module.exports = {
  validateSystem2EventV1
};

