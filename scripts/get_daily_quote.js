#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const LITERATURE_DIR = path.join(process.env.HOME || '', 'clawd/memory/literature');
const STATE_FILE = path.join(LITERATURE_DIR, 'state.json');
const MANIFEST_FILE = path.join(LITERATURE_DIR, 'quotes_manifest.json');
const DEFAULT_CHUNK_SIZE = 2000;

function parseArgs(argv) {
  const out = { check: false, rebuild: false, seed: null };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--check') out.check = true;
    else if (arg === '--rebuild') out.rebuild = true;
    else if (arg === '--seed' && argv[i + 1]) {
      out.seed = Number.parseInt(argv[i + 1], 10);
      i += 1;
    }
  }
  return out;
}

function createSeededRandom(seed) {
  let state = (Number.isInteger(seed) ? seed : 1) >>> 0;
  return () => {
    state = (1664525 * state + 1013904223) >>> 0;
    return state / 0x100000000;
  };
}

function listLiteratureFiles(literatureDir) {
  if (!fs.existsSync(literatureDir)) return [];
  return fs.readdirSync(literatureDir).filter((name) => name.endsWith('.txt')).sort();
}

function sourceFingerprint(literatureDir) {
  return listLiteratureFiles(literatureDir).map((file) => {
    const full = path.join(literatureDir, file);
    const stat = fs.statSync(full);
    return { file, size: stat.size, mtimeMs: stat.mtimeMs };
  });
}

function buildManifest(literatureDir, manifestPath = MANIFEST_FILE, chunkSize = DEFAULT_CHUNK_SIZE) {
  const files = [];
  for (const fp of sourceFingerprint(literatureDir)) {
    const chunks = [];
    const count = Math.max(1, Math.ceil(fp.size / chunkSize));
    for (let i = 0; i < count; i += 1) {
      const offset = i * chunkSize;
      const length = Math.min(chunkSize, Math.max(0, fp.size - offset));
      chunks.push({ offset, length: Math.max(0, length) });
    }
    files.push({ file: fp.file, size: fp.size, chunks });
  }
  const manifest = {
    version: 1,
    chunkSize,
    generatedAt: new Date().toISOString(),
    sourceFingerprint: sourceFingerprint(literatureDir),
    files
  };
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n', 'utf8');
  return manifest;
}

function loadManifest(manifestPath = MANIFEST_FILE) {
  if (!fs.existsSync(manifestPath)) return null;
  try {
    return JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  } catch (_) {
    return null;
  }
}

function manifestsMatch(a, b) {
  if (!Array.isArray(a) || !Array.isArray(b)) return false;
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i += 1) {
    if (a[i].file !== b[i].file) return false;
    if (Number(a[i].size) !== Number(b[i].size)) return false;
    if (Number(a[i].mtimeMs) !== Number(b[i].mtimeMs)) return false;
  }
  return true;
}

function loadOrBuildManifest({ literatureDir = LITERATURE_DIR, manifestPath = MANIFEST_FILE, rebuild = false, chunkSize = DEFAULT_CHUNK_SIZE }) {
  const fingerprint = sourceFingerprint(literatureDir);
  const existing = rebuild ? null : loadManifest(manifestPath);
  if (existing && manifestsMatch(existing.sourceFingerprint, fingerprint)) {
    return existing;
  }
  return buildManifest(literatureDir, manifestPath, chunkSize);
}

function readChunk(filePath, offset, length) {
  const size = Math.max(0, Number(length) || 0);
  if (size <= 0) return '';
  const fd = fs.openSync(filePath, 'r');
  try {
    const buf = Buffer.allocUnsafe(size);
    const bytesRead = fs.readSync(fd, buf, 0, size, Math.max(0, Number(offset) || 0));
    return buf.toString('utf8', 0, bytesRead);
  } finally {
    fs.closeSync(fd);
  }
}

function selectQuote(manifest, literatureDir = LITERATURE_DIR, rand = Math.random) {
  const files = Array.isArray(manifest?.files) ? manifest.files : [];
  if (files.length === 0) {
    throw new Error('No text files found.');
  }
  const file = files[Math.floor(rand() * files.length) % files.length];
  const chunks = Array.isArray(file.chunks) && file.chunks.length > 0
    ? file.chunks
    : [{ offset: 0, length: Math.max(0, Number(file.size) || 0) }];
  const chunk = chunks[Math.floor(rand() * chunks.length) % chunks.length];
  const fullPath = path.join(literatureDir, file.file);
  const text = readChunk(fullPath, chunk.offset, chunk.length || manifest.chunkSize || DEFAULT_CHUNK_SIZE);
  return { file: file.file, offset: chunk.offset, chunk: text };
}

function loadState(statePath = STATE_FILE) {
  if (!fs.existsSync(statePath)) return { lastQuoteDate: null, deliveredQuotes: [] };
  try {
    return JSON.parse(fs.readFileSync(statePath, 'utf8'));
  } catch (_) {
    return { lastQuoteDate: null, deliveredQuotes: [] };
  }
}

function saveState(state, statePath = STATE_FILE) {
  fs.writeFileSync(statePath, JSON.stringify(state, null, 2), 'utf8');
}

function main(argv = process.argv.slice(2)) {
  const args = parseArgs(argv);
  if (!fs.existsSync(LITERATURE_DIR)) {
    console.error('Literature directory not found. Run extraction first.');
    return 1;
  }

  const state = loadState(STATE_FILE);
  const today = new Date().toISOString().split('T')[0];
  if (args.check && state.lastQuoteDate === today) {
    console.log('ALREADY_DELIVERED');
    return 0;
  }

  const manifest = loadOrBuildManifest({
    literatureDir: LITERATURE_DIR,
    manifestPath: MANIFEST_FILE,
    rebuild: args.rebuild,
    chunkSize: DEFAULT_CHUNK_SIZE
  });

  const rand = Number.isInteger(args.seed) ? createSeededRandom(args.seed) : Math.random;
  const selected = selectQuote(manifest, LITERATURE_DIR, rand);

  console.log(`SOURCE: ${selected.file}`);
  console.log(`OFFSET: ${selected.offset}`);
  console.log('--- CHUNK ---');
  console.log(selected.chunk);
  console.log('--- END CHUNK ---');

  state.lastQuoteDate = today;
  saveState(state, STATE_FILE);
  return 0;
}

if (require.main === module) {
  process.exitCode = main();
}

module.exports = {
  DEFAULT_CHUNK_SIZE,
  MANIFEST_FILE,
  STATE_FILE,
  buildManifest,
  createSeededRandom,
  listLiteratureFiles,
  loadManifest,
  loadOrBuildManifest,
  manifestsMatch,
  parseArgs,
  selectQuote
};
