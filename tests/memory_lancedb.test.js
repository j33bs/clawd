#!/usr/bin/env node
'use strict';

/**
 * memory-lancedb — Tests
 *
 * CI-safe: uses null embedder (no API keys required) and a tmp directory.
 *
 * Run:
 *   node tests/memory_lancedb.test.js
 */

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { MemoryStore, loadMemoryConfig, createEmbedder, createNullEmbedder, NULL_DIMS } = require('../modules/memory-lancedb');

let passed = 0;
let failed = 0;
const failures = [];

function test(name, fn) {
  try {
    fn();
    passed++;
    console.log(`  pass: ${name}`);
  } catch (err) {
    failed++;
    failures.push({ name, error: err.message });
    console.error(`  FAIL: ${name} — ${err.message}`);
  }
}

async function testAsync(name, fn) {
  try {
    await fn();
    passed++;
    console.log(`  pass: ${name}`);
  } catch (err) {
    failed++;
    failures.push({ name, error: err.message });
    console.error(`  FAIL: ${name} — ${err.message}`);
  }
}

function tmpDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'memory-lancedb-test-'));
}

async function main() {

// ── Config tests ──────────────────────────────────────────────────────────────

console.log('\n── Config ──');

test('loadMemoryConfig returns expected shape', () => {
  const cfg = loadMemoryConfig({});
  assert.ok(cfg.lancedb.path);
  assert.ok(cfg.lancedb.table);
  assert.equal(typeof cfg.recallLimit, 'number');
  assert.ok(cfg.minimax);
  assert.ok(cfg.ollama);
});

test('loadMemoryConfig respects env overrides', () => {
  const cfg = loadMemoryConfig({
    MEMORY_LANCEDB_PATH: '/custom/path',
    MEMORY_LANCEDB_TABLE: 'custom_table',
    MEMORY_EMBEDDER: 'ollama',
    MEMORY_RECALL_LIMIT: '10'
  });
  assert.equal(cfg.lancedb.path, '/custom/path');
  assert.equal(cfg.lancedb.table, 'custom_table');
  assert.equal(cfg.embedder, 'ollama');
  assert.equal(cfg.recallLimit, 10);
});

test('loadMemoryConfig reads MiniMax key from OPENCLAW_MINIMAX_PORTAL_API_KEY', () => {
  const cfg = loadMemoryConfig({ OPENCLAW_MINIMAX_PORTAL_API_KEY: 'test-key' });
  assert.equal(cfg.minimax.apiKey, 'test-key');
});

// ── Embedder tests ────────────────────────────────────────────────────────────

console.log('\n── Embedder ──');

test('null embedder has correct dims', () => {
  const e = createNullEmbedder();
  assert.equal(e.dims, NULL_DIMS);
  assert.equal(e.name, 'null');
});

await testAsync('null embedder returns zero vectors', async () => {
  const e = createNullEmbedder();
  const vecs = await e.embed(['hello', 'world']);
  assert.equal(vecs.length, 2);
  for (const v of vecs) {
    assert.ok(v instanceof Float32Array);
    assert.equal(v.length, NULL_DIMS);
    assert.ok(v.every((x) => x === 0));
  }
});

test('createEmbedder selects null when MEMORY_EMBEDDER=null', () => {
  const cfg = loadMemoryConfig({ MEMORY_EMBEDDER: 'null' });
  const e = createEmbedder(cfg);
  assert.equal(e.name, 'null');
});

test('createEmbedder auto-selects ollama when no minimax key', () => {
  const cfg = loadMemoryConfig({ MEMORY_EMBEDDER: 'auto', OPENCLAW_MINIMAX_PORTAL_API_KEY: '' });
  const e = createEmbedder(cfg);
  assert.equal(e.name, 'ollama');
});

test('createEmbedder auto-selects minimax when key is present', () => {
  const cfg = loadMemoryConfig({
    MEMORY_EMBEDDER: 'auto',
    OPENCLAW_MINIMAX_PORTAL_API_KEY: 'sk-test'
  });
  const e = createEmbedder(cfg);
  assert.equal(e.name, 'minimax');
});

test('createEmbedder throws on unknown mode', () => {
  const cfg = loadMemoryConfig({ MEMORY_EMBEDDER: 'unknown' });
  assert.throws(() => createEmbedder(cfg), /Unknown embedder/);
});

// ── MemoryStore tests ─────────────────────────────────────────────────────────

console.log('\n── MemoryStore ──');

await testAsync('open creates DB directory', async () => {
  const dir = tmpDir();
  const dbPath = path.join(dir, 'lancedb');
  const cfg = loadMemoryConfig({ MEMORY_LANCEDB_PATH: dbPath, MEMORY_EMBEDDER: 'null' });
  const store = new MemoryStore(cfg, createNullEmbedder());
  await store.open();
  assert.ok(fs.existsSync(dbPath));
  await store.close();
  fs.rmSync(dir, { recursive: true });
});

await testAsync('remember + recall round-trip', async () => {
  const dir = tmpDir();
  const cfg = loadMemoryConfig({
    MEMORY_LANCEDB_PATH: path.join(dir, 'lancedb'),
    MEMORY_EMBEDDER: 'null',
    MEMORY_RECALL_LIMIT: '5'
  });
  const store = new MemoryStore(cfg, createNullEmbedder());
  await store.open();

  await store.remember({
    text: 'ITC signal was bullish on BTC',
    source: 'dali',
    tags: ['itc', 'btc'],
    metadata: { session: '2026-02-19' }
  });

  const hits = await store.recall('bitcoin sentiment');
  assert.ok(hits.length >= 1);
  const hit = hits[0];
  assert.equal(hit.text, 'ITC signal was bullish on BTC');
  assert.equal(hit.source, 'dali');
  assert.deepEqual(hit.tags, ['itc', 'btc']);
  assert.deepEqual(hit.metadata, { session: '2026-02-19' });
  assert.equal(typeof hit.score, 'number');

  await store.close();
  fs.rmSync(dir, { recursive: true });
});

await testAsync('recall returns [] before any remember()', async () => {
  const dir = tmpDir();
  const cfg = loadMemoryConfig({
    MEMORY_LANCEDB_PATH: path.join(dir, 'lancedb'),
    MEMORY_EMBEDDER: 'null'
  });
  const store = new MemoryStore(cfg, createNullEmbedder());
  await store.open();
  const hits = await store.recall('anything');
  assert.deepEqual(hits, []);
  await store.close();
  fs.rmSync(dir, { recursive: true });
});

await testAsync('multiple entries, recall limit respected', async () => {
  const dir = tmpDir();
  const cfg = loadMemoryConfig({
    MEMORY_LANCEDB_PATH: path.join(dir, 'lancedb'),
    MEMORY_EMBEDDER: 'null',
    MEMORY_RECALL_LIMIT: '2'
  });
  const store = new MemoryStore(cfg, createNullEmbedder());
  await store.open();

  for (let i = 0; i < 5; i++) {
    await store.remember({ text: `memory ${i}`, source: 'test' });
  }

  const hits = await store.recall('memory', { k: 2 });
  assert.equal(hits.length, 2);

  await store.close();
  fs.rmSync(dir, { recursive: true });
});

await testAsync('store persists across open/close cycles', async () => {
  const dir = tmpDir();
  const dbPath = path.join(dir, 'lancedb');
  const makeStore = () => {
    const cfg = loadMemoryConfig({ MEMORY_LANCEDB_PATH: dbPath, MEMORY_EMBEDDER: 'null' });
    return new MemoryStore(cfg, createNullEmbedder());
  };

  // Session 1: write
  const s1 = makeStore();
  await s1.open();
  await s1.remember({ text: 'persistent memory', source: 'test' });
  await s1.close();

  // Session 2: read back
  const s2 = makeStore();
  await s2.open();
  const hits = await s2.recall('persistent');
  assert.ok(hits.some((h) => h.text === 'persistent memory'));
  await s2.close();

  fs.rmSync(dir, { recursive: true });
});

await testAsync('remember throws if text is missing', async () => {
  const dir = tmpDir();
  const cfg = loadMemoryConfig({ MEMORY_LANCEDB_PATH: path.join(dir, 'lancedb'), MEMORY_EMBEDDER: 'null' });
  const store = new MemoryStore(cfg, createNullEmbedder());
  await store.open();
  await assert.rejects(() => store.remember({ source: 'test' }), /text is required/);
  await store.close();
  fs.rmSync(dir, { recursive: true });
});

await testAsync('recall throws if store not opened', async () => {
  const cfg = loadMemoryConfig({ MEMORY_EMBEDDER: 'null' });
  const store = new MemoryStore(cfg, createNullEmbedder());
  await assert.rejects(() => store.recall('test'), /not open/);
});

// ── Summary ───────────────────────────────────────────────────────────────────

console.log(`\n${passed} passed, ${failed} failed\n`);
if (failures.length) {
  console.error('Failures:');
  for (const f of failures) console.error(`  ${f.name}: ${f.error}`);
  process.exit(1);
}

} // end main

main().catch((err) => { console.error('Unhandled error:', err); process.exit(1); });
