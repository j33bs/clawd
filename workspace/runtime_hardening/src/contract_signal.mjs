import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MODULE_ROOT = path.resolve(HERE, '..', '..', '..');

function utcNowZ() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
}

function hasContractState(rootDir) {
  try {
    return fs.existsSync(path.join(rootDir, 'workspace', 'state_runtime', 'contract'));
  } catch {
    return false;
  }
}

function resolveWorkspaceRoot() {
  const explicitWorkspace = String(process.env.OPENCLAW_WORKSPACE_ROOT || '').trim();
  if (explicitWorkspace) {
    return path.resolve(explicitWorkspace);
  }

  try {
    const cwdRoot = process.cwd();
    if (hasContractState(cwdRoot)) {
      return cwdRoot;
    }
  } catch {
    // fall through
  }

  return MODULE_ROOT;
}

function resolveSignalPath() {
  const stateDir = String(process.env.OPENCLAW_CONTRACT_STATE_DIR || '').trim();
  if (stateDir) {
    return path.join(stateDir, 'signals', 'activity.jsonl');
  }
  const workspaceRoot = resolveWorkspaceRoot();
  return path.join(workspaceRoot, 'workspace', 'state_runtime', 'contract', 'signals', 'activity.jsonl');
}

let lastWriteMs = 0;

export function getResolvedSignalPath() {
  return resolveSignalPath();
}

export function appendContractSignal(kind, meta = {}, { minIntervalMs = 10_000 } = {}) {
  const now = Date.now();
  const interval = Number.isFinite(Number(minIntervalMs)) ? Number(minIntervalMs) : 10_000;
  if (interval > 0 && now - lastWriteMs < interval) {
    return { ok: true, skipped: true, reason: 'rate_limited' };
  }

  const signalPath = resolveSignalPath();
  const event = {
    ts: utcNowZ(),
    kind,
    meta,
  };

  try {
    fs.mkdirSync(path.dirname(signalPath), { recursive: true });
    fs.appendFileSync(signalPath, JSON.stringify(event) + '\n', { encoding: 'utf8' });
    lastWriteMs = now;
    return { ok: true, skipped: false, path: signalPath };
  } catch (error) {
    return {
      ok: false,
      skipped: false,
      error: String(error?.message || error),
    };
  }
}

export function _resetRateLimitForTest() {
  lastWriteMs = 0;
}
