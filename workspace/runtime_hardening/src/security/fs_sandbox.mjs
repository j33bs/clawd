import fs from 'node:fs';
import path from 'node:path';

function ensureRootExists(rootPath) {
  if (!rootPath || typeof rootPath !== 'string') {
    throw new Error('workspace root must be a non-empty string');
  }
  if (!fs.existsSync(rootPath)) {
    throw new Error(`workspace root does not exist: ${rootPath}`);
  }
}

function realpathForMaybeMissing(targetPath) {
  if (fs.existsSync(targetPath)) return fs.realpathSync(targetPath);
  const suffix = [];
  let cursor = path.resolve(targetPath);

  while (!fs.existsSync(cursor)) {
    const parent = path.dirname(cursor);
    if (parent === cursor) {
      throw new Error(`unable to resolve path: ${targetPath}`);
    }
    suffix.unshift(path.basename(cursor));
    cursor = parent;
  }

  const existing = fs.realpathSync(cursor);
  return path.resolve(existing, ...suffix);
}

function normalizeWithTrailingSep(value) {
  return value.endsWith(path.sep) ? value : `${value}${path.sep}`;
}

function isPathWithinRoot(rootPath, targetPath) {
  ensureRootExists(rootPath);
  const rootReal = fs.realpathSync(path.resolve(rootPath));
  const targetReal = realpathForMaybeMissing(path.resolve(targetPath));
  if (targetReal === rootReal) return true;
  return targetReal.startsWith(normalizeWithTrailingSep(rootReal));
}

function assertPathWithinRoot(rootPath, targetPath, options = {}) {
  const allowOutsideWorkspace = options.allowOutsideWorkspace === true;
  const absoluteTarget = path.resolve(targetPath);
  if (allowOutsideWorkspace) return absoluteTarget;

  if (!isPathWithinRoot(rootPath, absoluteTarget)) {
    const rootReal = fs.realpathSync(path.resolve(rootPath));
    const targetReal = realpathForMaybeMissing(absoluteTarget);
    throw new Error(`path escapes workspace root (root=${rootReal}, target=${targetReal})`);
  }

  return absoluteTarget;
}

function ensureDirectoryWithinRoot(rootPath, targetPath, options = {}) {
  const absolute = assertPathWithinRoot(rootPath, targetPath, options);
  fs.mkdirSync(absolute, { recursive: true });
  return absolute;
}

export { assertPathWithinRoot, ensureDirectoryWithinRoot, isPathWithinRoot, realpathForMaybeMissing };
