// guarded_fs.js
// Guarded filesystem helpers to keep reads/writes within the repo workspace.

const fs = require('fs');
const path = require('path');

const WORKSPACE_ROOT = resolveWorkspaceRoot();
const DENY_SUBSTRINGS = [
  '/library/',
  'autosave',
  'containers',
  'deriveddata'
];

function resolveWorkspaceRoot() {
  const envRoot = process.env.WORKSPACE_ROOT;
  if (envRoot && envRoot.trim().length > 0) {
    return path.resolve(envRoot.trim());
  }
  return path.resolve(__dirname, '..');
}

function isDeniedPath(resolvedPath) {
  const lower = resolvedPath.toLowerCase();
  return DENY_SUBSTRINGS.some(fragment => lower.includes(fragment));
}

function isWithinWorkspace(resolvedPath) {
  return resolvedPath === WORKSPACE_ROOT || resolvedPath.startsWith(WORKSPACE_ROOT + path.sep);
}

function guardPath(inputPath, options = {}) {
  const resolvedPath = path.isAbsolute(inputPath)
    ? path.resolve(inputPath)
    : path.resolve(WORKSPACE_ROOT, inputPath);

  if (isDeniedPath(resolvedPath)) {
    return { allowed: false, reason: 'denied-subpath', resolvedPath };
  }

  if (!options.allowOutsideWorkspace && !isWithinWorkspace(resolvedPath)) {
    return { allowed: false, reason: 'outside-workspace', resolvedPath };
  }

  return { allowed: true, reason: null, resolvedPath };
}

function logDenied(reason, inputPath, resolvedPath) {
  const normalizedInput = inputPath || '<empty>';
  console.warn(`[guarded-fs] denied ${reason}: ${normalizedInput} -> ${resolvedPath}`);
}

function resolveWorkspacePath(inputPath, options = {}) {
  const guard = guardPath(inputPath, options);
  if (!guard.allowed) {
    logDenied(guard.reason, inputPath, guard.resolvedPath);
    return null;
  }
  return guard.resolvedPath;
}

function resolveWorkspacePathOrFallback(inputPath, fallbackRelative, options = {}) {
  const primaryPath = resolveWorkspacePath(inputPath, options);
  if (primaryPath) {
    return { resolvedPath: primaryPath, usedFallback: false, deniedReason: null };
  }

  const fallbackPath = resolveWorkspacePath(fallbackRelative, { allowOutsideWorkspace: false });
  return { resolvedPath: fallbackPath, usedFallback: true, deniedReason: 'denied' };
}

function readFileSync(inputPath, options = {}) {
  const guard = guardPath(inputPath, options);
  if (!guard.allowed) {
    logDenied(guard.reason, inputPath, guard.resolvedPath);
    if (options.fallbackPath) {
      return readFileSync(options.fallbackPath, { ...options, fallbackPath: null });
    }
    return null;
  }
  return fs.readFileSync(guard.resolvedPath, options.encoding || 'utf8');
}

async function readFile(inputPath, options = {}) {
  const guard = guardPath(inputPath, options);
  if (!guard.allowed) {
    logDenied(guard.reason, inputPath, guard.resolvedPath);
    if (options.fallbackPath) {
      return readFile(options.fallbackPath, { ...options, fallbackPath: null });
    }
    return null;
  }
  return fs.promises.readFile(guard.resolvedPath, options.encoding || 'utf8');
}

function writeFileSync(inputPath, content, options = {}) {
  const guard = guardPath(inputPath, options);
  if (!guard.allowed) {
    logDenied(guard.reason, inputPath, guard.resolvedPath);
    throw new Error(`Write blocked by guarded-fs: ${guard.reason}`);
  }
  return fs.writeFileSync(guard.resolvedPath, content, options);
}

async function writeFile(inputPath, content, options = {}) {
  const guard = guardPath(inputPath, options);
  if (!guard.allowed) {
    logDenied(guard.reason, inputPath, guard.resolvedPath);
    throw new Error(`Write blocked by guarded-fs: ${guard.reason}`);
  }
  return fs.promises.writeFile(guard.resolvedPath, content, options);
}

function existsSync(inputPath, options = {}) {
  const guard = guardPath(inputPath, options);
  if (!guard.allowed) {
    logDenied(guard.reason, inputPath, guard.resolvedPath);
    return false;
  }
  return fs.existsSync(guard.resolvedPath);
}

function mkdirSync(inputPath, options = {}) {
  const guard = guardPath(inputPath, options);
  if (!guard.allowed) {
    logDenied(guard.reason, inputPath, guard.resolvedPath);
    throw new Error(`Directory create blocked by guarded-fs: ${guard.reason}`);
  }
  return fs.mkdirSync(guard.resolvedPath, options);
}

function readdirSync(inputPath, options = {}) {
  const guard = guardPath(inputPath, options);
  if (!guard.allowed) {
    logDenied(guard.reason, inputPath, guard.resolvedPath);
    return [];
  }
  return fs.readdirSync(guard.resolvedPath, options);
}

function statSync(inputPath) {
  const guard = guardPath(inputPath);
  if (!guard.allowed) {
    logDenied(guard.reason, inputPath, guard.resolvedPath);
    return null;
  }
  return fs.statSync(guard.resolvedPath);
}

function ensureDirSync(inputPath) {
  if (!inputPath) {
    throw new Error('ensureDirSync requires a path');
  }
  if (!existsSync(inputPath)) {
    mkdirSync(inputPath, { recursive: true });
  }
}

function readJsonFileSync(inputPath, options = {}) {
  const content = readFileSync(inputPath, options);
  if (content === null) {
    return null;
  }
  return JSON.parse(content);
}

async function readJsonFile(inputPath, options = {}) {
  const content = await readFile(inputPath, options);
  if (content === null) {
    return null;
  }
  return JSON.parse(content);
}

function writeJsonFileSync(inputPath, data, options = {}) {
  const json = JSON.stringify(data, null, 2);
  return writeFileSync(inputPath, json, options);
}

async function writeJsonFile(inputPath, data, options = {}) {
  const json = JSON.stringify(data, null, 2);
  return writeFile(inputPath, json, options);
}

module.exports = {
  WORKSPACE_ROOT,
  guardPath,
  resolveWorkspacePath,
  resolveWorkspacePathOrFallback,
  readFileSync,
  readFile,
  writeFileSync,
  writeFile,
  existsSync,
  mkdirSync,
  readdirSync,
  statSync,
  ensureDirSync,
  readJsonFileSync,
  readJsonFile,
  writeJsonFileSync,
  writeJsonFile
};
