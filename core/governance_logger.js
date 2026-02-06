const path = require('path');
const { appendJsonArray } = require('../scripts/guarded_fs');

class GovernanceLogger {
  constructor(options = {}) {
    this.persist = options.persist !== false;
  }

  async appendJsonLog(relativePath, entry) {
    if (!this.persist) {
      return;
    }

    try {
      await appendJsonArray(relativePath, entry);
    } catch (error) {
      const message = error && error.message ? error.message : String(error);
      console.warn(`[governance-logger] append failed for ${relativePath}: ${message}`);
    }
  }

  async logFallbackEvent(event) {
    await this.appendJsonLog(path.join('logs', 'fallback_events.json'), event);
  }

  async logNotification(event) {
    await this.appendJsonLog(path.join('logs', 'notifications.json'), event);
  }
}

module.exports = GovernanceLogger;
