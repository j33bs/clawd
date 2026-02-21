'use strict';

const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const {
  buildManifest,
  createSeededRandom,
  loadOrBuildManifest,
  selectQuote
} = require('../scripts/get_daily_quote');

function makeFixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'quote-manifest-'));
  const literatureDir = path.join(root, 'literature');
  fs.mkdirSync(literatureDir, { recursive: true });
  fs.writeFileSync(path.join(literatureDir, 'a.txt'), 'alpha '.repeat(600), 'utf8');
  fs.writeFileSync(path.join(literatureDir, 'b.txt'), 'beta '.repeat(700), 'utf8');
  return { root, literatureDir };
}

function testManifestBuildAndReuse() {
  const { literatureDir } = makeFixture();
  const manifestPath = path.join(literatureDir, 'quotes_manifest.json');
  const first = buildManifest(literatureDir, manifestPath, 2000);
  const second = loadOrBuildManifest({ literatureDir, manifestPath, rebuild: false, chunkSize: 2000 });
  assert.ok(first.files.length >= 2);
  assert.strictEqual(second.files.length, first.files.length);
  assert.ok(fs.existsSync(manifestPath));
  console.log('PASS get_daily_quote manifest build + reuse');
}

function testSeededSelectionDeterministic() {
  const { literatureDir } = makeFixture();
  const manifestPath = path.join(literatureDir, 'quotes_manifest.json');
  const manifest = loadOrBuildManifest({ literatureDir, manifestPath, rebuild: true, chunkSize: 2000 });
  const first = selectQuote(manifest, literatureDir, createSeededRandom(42));
  const second = selectQuote(manifest, literatureDir, createSeededRandom(42));
  assert.strictEqual(first.file, second.file);
  assert.strictEqual(first.offset, second.offset);
  assert.strictEqual(first.chunk, second.chunk);
  console.log('PASS get_daily_quote deterministic seeded selection');
}

testManifestBuildAndReuse();
testSeededSelectionDeterministic();
