const path = require('path');
const fs = require('fs');

const WORKSPACE_ROOT = path.resolve(__dirname, '..');

function resolveWorkspacePath(inputPath) {
  const resolved = path.isAbsolute(inputPath)
    ? path.resolve(inputPath)
    : path.resolve(WORKSPACE_ROOT, inputPath);

  if (resolved === WORKSPACE_ROOT || resolved.startsWith(WORKSPACE_ROOT + path.sep)) {
    return resolved;
  }

  return null;
}

function ensureDirSync(inputPath) {
  if (!fs.existsSync(inputPath)) {
    fs.mkdirSync(inputPath, { recursive: true });
  }
}

async function readJsonFile(inputPath) {
  const content = await fs.promises.readFile(inputPath, 'utf8');
  return JSON.parse(content);
}

async function writeJsonFile(inputPath, data) {
  const content = JSON.stringify(data, null, 2);
  await fs.promises.writeFile(inputPath, content);
}

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
