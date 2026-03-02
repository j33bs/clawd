'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const SUBPROCESS_UNAVAILABLE_REASON = 'subprocess spawn unavailable in this environment';

function canSpawnSubprocess() {
  const probe = spawnSync(process.execPath, ['-e', 'process.exit(0)'], { encoding: 'utf8' });
  if (probe.error) {
    const code = probe.error && probe.error.code ? String(probe.error.code) : 'UNKNOWN';
    return { ok: false, reason: `${SUBPROCESS_UNAVAILABLE_REASON} (${code})` };
  }
  return { ok: true, reason: '' };
}

function hasCommand(cmd) {
  if (!cmd || typeof cmd !== 'string') return false;

  const pathValue = process.env.PATH || '';
  const directories = pathValue.split(path.delimiter).filter(Boolean);
  const extensions = process.platform === 'win32'
    ? (process.env.PATHEXT || '.EXE;.CMD;.BAT;.COM').split(';').filter(Boolean)
    : [''];

  for (const directory of directories) {
    for (const ext of extensions) {
      const candidate = path.join(directory, process.platform === 'win32' ? `${cmd}${ext}` : cmd);
      try {
        fs.accessSync(candidate, fs.constants.X_OK);
        return true;
      } catch (_error) {
        // Keep scanning.
      }
    }
  }
  return false;
}

function isRestrictedContext() {
  if (process.env.OPENCLAW_RESTRICTED_CONTEXT === '1') return true;
  return !canSpawnSubprocess().ok;
}

function requireSubprocessOrSkip(t, label) {
  const capability = canSpawnSubprocess();
  if (capability.ok) return true;
  const reason = label ? `${SUBPROCESS_UNAVAILABLE_REASON} (${label})` : SUBPROCESS_UNAVAILABLE_REASON;
  t.skip(reason);
  return false;
}

module.exports = {
  canSpawnSubprocess,
  hasCommand,
  isRestrictedContext,
  requireSubprocessOrSkip,
  SUBPROCESS_UNAVAILABLE_REASON,
};
