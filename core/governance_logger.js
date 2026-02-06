const path = require('path');
const {
  resolveWorkspacePath,
  ensureDirSync,
  readJsonFile,
  writeJsonFile
} = require('../scripts/guarded_fs');

class GovernanceLogger {
  constructor(options = {}) {
    this.persist = options.persist !== false;
  }

  async appendJsonLog(relativePath, entry) {
    if (!this.persist) {
      return;
    }

    const logPath = resolveWorkspacePath(relativePath);
    if (!logPath) {
      return;
    }

    ensureDirSync(path.dirname(logPath));
    let existing = null;
    try {
      existing = await readJsonFile(logPath);
    } catch (error) {
      existing = [];
    }
    const events = Array.isArray(existing) ? existing : [];
    events.push(entry);
    await writeJsonFile(logPath, events);
  }

  async logFallbackEvent(event) {
    await this.appendJsonLog(path.join('logs', 'fallback_events.json'), event);
  }

  async logNotification(event) {
    await this.appendJsonLog(path.join('logs', 'notifications.json'), event);
  }
}

module.exports = GovernanceLogger;
