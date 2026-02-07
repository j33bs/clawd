const fs = require('fs');
const path = require('path');
const { resolveWorkspacePath } = require('../../scripts/guarded_fs');

const DEFAULT_TRACE_PATH = 'logs/chain_runs/chain_trace.jsonl';
const DEFAULT_MAX_ENTRIES = 2000;

async function ensureDir(dirPath) {
  await fs.promises.mkdir(dirPath, { recursive: true });
}

async function acquireLock(lockPath, retries = 10, delayMs = 25) {
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      const handle = await fs.promises.open(lockPath, 'wx');
      return handle;
    } catch (error) {
      if (error && error.code === 'EEXIST' && attempt < retries) {
        await new Promise((resolve) => setTimeout(resolve, delayMs * (attempt + 1)));
        continue;
      }
      throw error;
    }
  }
  throw new Error(`Failed to acquire lock: ${lockPath}`);
}

async function readLines(filePath) {
  try {
    const content = await fs.promises.readFile(filePath, 'utf8');
    return content.split('\n').filter(Boolean);
  } catch (error) {
    if (error && error.code === 'ENOENT') {
      return [];
    }
    throw error;
  }
}

async function writeLines(filePath, lines) {
  const content = lines.join('\n') + (lines.length > 0 ? '\n' : '');
  await fs.promises.writeFile(filePath, content, 'utf8');
}

async function appendTrace(entry, options = {}) {
  const relativePath = options.tracePath || DEFAULT_TRACE_PATH;
  const targetPath = resolveWorkspacePath(relativePath);
  if (!targetPath) {
    throw new Error(`Path outside workspace: ${relativePath}`);
  }

  const dirPath = path.dirname(targetPath);
  await ensureDir(dirPath);

  const lockPath = `${targetPath}.lock`;
  const lockHandle = await acquireLock(lockPath);

  try {
    const maxEntries = Number(options.maxEntries ?? DEFAULT_MAX_ENTRIES);
    const lines = await readLines(targetPath);
    lines.push(JSON.stringify(entry));

    if (Number.isInteger(maxEntries) && maxEntries > 0 && lines.length > maxEntries) {
      lines.splice(0, lines.length - maxEntries);
    }

    await writeLines(targetPath, lines);
  } finally {
    try {
      await lockHandle.close();
    } finally {
      await fs.promises.unlink(lockPath).catch(() => {});
    }
  }
}

module.exports = {
  DEFAULT_TRACE_PATH,
  appendTrace
};
