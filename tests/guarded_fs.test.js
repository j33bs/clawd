const assert = require('assert');
const fs = require('fs');

const { appendJsonArray, resolveWorkspacePath } = require('../scripts/guarded_fs');

const TEMP_BASE_REL = '.tmp_test_logs';
const TEMP_ROOT_REL = '.tmp_test_logs/guarded_fs';
const TEMP_BASE = resolveWorkspacePath(TEMP_BASE_REL);
const TEMP_ROOT = resolveWorkspacePath(TEMP_ROOT_REL);

if (!TEMP_ROOT) {
  throw new Error('Failed to resolve temp test path inside workspace');
}

async function cleanup() {
  await fs.promises.rm(TEMP_ROOT, { recursive: true, force: true });
  if (TEMP_BASE) {
    await fs.promises.rm(TEMP_BASE, { recursive: true, force: true });
  }
}

async function readJson(relativePath) {
  const absolutePath = resolveWorkspacePath(relativePath);
  assert.ok(absolutePath, `Expected workspace path for ${relativePath}`);
  const content = await fs.promises.readFile(absolutePath, 'utf8');
  return JSON.parse(content);
}

async function fileExists(relativePath) {
  const absolutePath = resolveWorkspacePath(relativePath);
  assert.ok(absolutePath, `Expected workspace path for ${relativePath}`);
  try {
    await fs.promises.access(absolutePath);
    return true;
  } catch (error) {
    return false;
  }
}

async function runTest(name, fn) {
  try {
    await fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    console.error(`  ${error.message}`);
    throw error;
  }
}

async function testCreatesDirectoryAndFile() {
  const relativePath = `${TEMP_ROOT_REL}/nested/logs/events.json`;
  await appendJsonArray(relativePath, { id: 1, name: 'first' });

  assert.strictEqual(await fileExists(relativePath), true, 'expected log file to be created');
  const value = await readJson(relativePath);
  assert.strictEqual(Array.isArray(value), true);
  assert.strictEqual(value.length, 1);
  assert.deepStrictEqual(value[0], { id: 1, name: 'first' });
}

async function testSuccessiveAppendsOrder() {
  const relativePath = `${TEMP_ROOT_REL}/order/events.json`;
  const entries = [{ index: 1 }, { index: 2 }, { index: 3 }];

  for (const entry of entries) {
    await appendJsonArray(relativePath, entry);
  }

  const value = await readJson(relativePath);
  assert.deepStrictEqual(value, entries);
}

async function testMaxEntriesTrimming() {
  const relativePath = `${TEMP_ROOT_REL}/trim/events.json`;

  for (let i = 1; i <= 5; i += 1) {
    await appendJsonArray(relativePath, { id: i }, { maxEntries: 3 });
  }

  const value = await readJson(relativePath);
  assert.strictEqual(value.length, 3);
  assert.deepStrictEqual(value, [{ id: 3 }, { id: 4 }, { id: 5 }]);
}

async function testNoPartialJsonAfterEachAppend() {
  const relativePath = `${TEMP_ROOT_REL}/atomic/events.json`;
  const absolutePath = resolveWorkspacePath(relativePath);
  assert.ok(absolutePath, 'Expected absolute path for atomic test');

  for (let i = 1; i <= 15; i += 1) {
    await appendJsonArray(relativePath, { id: i });

    const raw = await fs.promises.readFile(absolutePath, 'utf8');
    const parsed = JSON.parse(raw);
    assert.strictEqual(Array.isArray(parsed), true);
    assert.strictEqual(parsed[parsed.length - 1].id, i);

    const lockExists = await fileExists(`${relativePath}.lock`);
    assert.strictEqual(lockExists, false, 'lock file should be cleaned up after append');
  }
}

async function main() {
  await cleanup();

  try {
    await runTest('appendJsonArray creates directories and file', testCreatesDirectoryAndFile);
    await runTest('successive appends keep JSON array order', testSuccessiveAppendsOrder);
    await runTest('maxEntries trimming keeps last N entries', testMaxEntriesTrimming);
    await runTest('append path remains parseable after each append', testNoPartialJsonAfterEachAppend);
  } finally {
    await cleanup();
  }
}

main().catch(() => {
  process.exit(1);
});
