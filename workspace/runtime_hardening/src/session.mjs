import { getConfig } from './config.mjs';
import { logger as rootLogger } from './log.mjs';

function now() {
  return Date.now();
}

function closeTransportMaybe(session, log) {
  const closeFn = session?.transport?.close;
  if (typeof closeFn !== 'function') return Promise.resolve();

  return Promise.resolve()
    .then(() => closeFn.call(session.transport))
    .catch((error) => {
      log.warn('session_transport_close_failed', {
        sessionId: session.id,
        error
      });
    });
}

class SessionManager {
  constructor(options = {}) {
    const config = options.config || getConfig();
    this.log = (options.logger || rootLogger).child({ module: 'session-manager' });
    this.sessionTtlMs = options.sessionTtlMs || config.sessionTtlMs;
    this.maxSessions = options.maxSessions || config.sessionMax;
    this.historyMaxMessages = options.historyMaxMessages || config.historyMaxMessages;
    this.sessions = new Map();
    this._timer = null;

    const interval = options.sweepIntervalMs || Math.max(1_000, Math.min(60_000, Math.floor(this.sessionTtlMs / 2)));
    this._timer = setInterval(() => {
      void this.sweepExpired();
    }, interval);
    if (typeof this._timer.unref === 'function') {
      this._timer.unref();
    }
  }

  count() {
    return this.sessions.size;
  }

  has(sessionId) {
    return this.sessions.has(sessionId);
  }

  getSession(sessionId) {
    return this.sessions.get(sessionId);
  }

  getOrCreateSession(sessionId, init = {}) {
    if (!sessionId || typeof sessionId !== 'string') {
      throw new Error('sessionId must be a non-empty string');
    }

    const existing = this.sessions.get(sessionId);
    if (existing) {
      existing.lastTouchedAt = now();
      if (init.transport) existing.transport = init.transport;
      return existing;
    }

    this._evictOverflow(1);

    const session = {
      id: sessionId,
      createdAt: now(),
      lastTouchedAt: now(),
      history: Array.isArray(init.history) ? init.history.slice(-this.historyMaxMessages) : [],
      transport: init.transport
    };

    this.sessions.set(sessionId, session);
    return session;
  }

  appendHistory(sessionId, message) {
    const session = this.getOrCreateSession(sessionId);
    session.lastTouchedAt = now();
    session.history.push(message);
    if (session.history.length > this.historyMaxMessages) {
      session.history.splice(0, session.history.length - this.historyMaxMessages);
    }
  }

  touch(sessionId) {
    const session = this.sessions.get(sessionId);
    if (session) session.lastTouchedAt = now();
  }

  async closeSession(sessionId) {
    const session = this.sessions.get(sessionId);
    if (!session) return false;
    this.sessions.delete(sessionId);
    await closeTransportMaybe(session, this.log);
    return true;
  }

  async sweepExpired(cutoffNow = now()) {
    const expired = [];
    for (const [sessionId, session] of this.sessions.entries()) {
      if (cutoffNow - session.lastTouchedAt > this.sessionTtlMs) {
        expired.push(sessionId);
      }
    }

    for (const sessionId of expired) {
      await this.closeSession(sessionId);
    }

    if (expired.length > 0) {
      this.log.debug('session_evicted_by_ttl', { count: expired.length });
    }

    return expired.length;
  }

  async shutdown() {
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }

    const ids = [...this.sessions.keys()];
    for (const sessionId of ids) {
      await this.closeSession(sessionId);
    }
  }

  _evictOverflow(incomingCount) {
    const overflow = this.sessions.size + incomingCount - this.maxSessions;
    if (overflow <= 0) return;

    const sorted = [...this.sessions.values()].sort((a, b) => a.lastTouchedAt - b.lastTouchedAt);
    for (let i = 0; i < overflow; i += 1) {
      const victim = sorted[i];
      if (!victim) continue;
      this.sessions.delete(victim.id);
      void closeTransportMaybe(victim, this.log);
    }
  }
}

export { SessionManager };
