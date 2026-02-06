const fs = require('fs');
const path = require('path');

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

async function ensureDir(dirPath) {
  await fs.promises.mkdir(dirPath, { recursive: true });
}

async function sleep(ms) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function acquireLock(lockPath, options = {}) {
  const retries = Number(options.retries ?? 15);
  const delayMs = Number(options.delayMs ?? 20);

  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      const handle = await fs.promises.open(lockPath, 'wx');
      return handle;
    } catch (error) {
      if (error && error.code === 'EEXIST' && attempt < retries) {
        await sleep(delayMs * (attempt + 1));
        continue;
      }
      throw error;
    }
  }

  throw new Error(`Failed to acquire lock: ${lockPath}`);
}

async function readJsonArray(inputPath) {
  try {
    const content = await fs.promises.readFile(inputPath, 'utf8');
    const parsed = JSON.parse(content);
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    if (error && error.code === 'ENOENT') {
      return [];
    }
    return [];
  }
}

async function appendJsonArray(relativePath, entry, options = {}) {
  const targetPath = resolveWorkspacePath(relativePath);
  if (!targetPath) {
    throw new Error(`Path outside workspace: ${relativePath}`);
  }

  const dirPath = path.dirname(targetPath);
  await ensureDir(dirPath);

  const lockPath = `${targetPath}.lock`;
  const lockHandle = await acquireLock(lockPath, options.lock);

  try {
    const data = await readJsonArray(targetPath);
    data.push(entry);
    if (Number.isInteger(options.maxEntries) && options.maxEntries > 0 && data.length > options.maxEntries) {
      data.splice(0, data.length - options.maxEntries);
    }

    const tempPath = `${targetPath}.${process.pid}.${Date.now()}.tmp`;
    const content = JSON.stringify(data, null, 2);
    await fs.promises.writeFile(tempPath, content, 'utf8');
    await fs.promises.rename(tempPath, targetPath);
  } finally {
    try {
      await lockHandle.close();
    } finally {
      await fs.promises.unlink(lockPath).catch(() => {});
    }
  }
}

module.exports = {
  WORKSPACE_ROOT,
  resolveWorkspacePath,
  appendJsonArray
};
