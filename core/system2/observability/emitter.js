'use strict';

const { deepRedact } = require('./redaction');

function makeEmitter(options) {
  const enabled = options && options.enabled === true;
  const strict = options && options.strict === true;
  const sink = options && options.sink;
  const nowFn = (options && options.nowFn) || (() => new Date());

  return async function emitSystem2Event(eventType, payload, context) {
    if (!enabled) return;

    const now = nowFn();
    const ts = (now && typeof now.toISOString === 'function') ? now.toISOString() : String(now);

    const event = {
      type: 'system2_event_v1',
      version: '1',
      ts_utc: ts,
      event_type: String(eventType || ''),
      level: 'info',
      payload: deepRedact(payload || {}, 'payload'),
      context: context || {}
    };

    if (!sink || typeof sink.appendEvent !== 'function') {
      if (strict) {
        const err = new Error('sink missing');
        err.code = 'SINK_MISSING';
        throw err;
      }
      return;
    }

    try {
      await sink.appendEvent(event);
    } catch (err) {
      if (strict) throw err;
    }
  };
}

module.exports = {
  makeEmitter
};

