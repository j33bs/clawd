'use strict';

const fs = require('node:fs');
const path = require('node:path');

function loadManifest(manifestPath) {
  if (!fs.existsSync(manifestPath)) {
    return {
      version: 1,
      updated_at: null,
      sources: []
    };
  }
  return JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
}

function normalizeSource(source) {
  return {
    id: String(source.id || '').trim(),
    title: String(source.title || '').trim(),
    year: source.year == null ? null : Number(source.year),
    venue: source.venue == null ? null : String(source.venue),
    doi: source.doi == null ? null : String(source.doi),
    pmid: source.pmid == null ? null : String(source.pmid),
    local_path: String(source.local_path || '').trim(),
    notes: source.notes == null ? '' : String(source.notes),
    claims: Array.isArray(source.claims)
      ? source.claims.map((claim) => String(claim || '').trim()).filter(Boolean)
      : []
  };
}

function validateSource(source) {
  if (!source.id) {
    throw new Error('Each source requires id');
  }
  if (!source.title) {
    throw new Error(`Source ${source.id} requires title`);
  }
  if (!source.local_path) {
    throw new Error(`Source ${source.id} requires local_path`);
  }
}

function ingestSources(options = {}) {
  const manifestPath = options.manifestPath || path.join(process.cwd(), 'sys', 'knowledge', 'breath', 'evidence', 'manifest.json');
  const sourceManifestPath = options.sourceManifestPath;
  if (!sourceManifestPath) {
    throw new Error('sourceManifestPath is required');
  }

  const manifest = loadManifest(manifestPath);
  const incoming = JSON.parse(fs.readFileSync(sourceManifestPath, 'utf8'));
  const incomingSources = Array.isArray(incoming.sources) ? incoming.sources : incoming;
  if (!Array.isArray(incomingSources)) {
    throw new Error('Source manifest must be an array or { sources: [] }');
  }

  const sourceMap = new Map((manifest.sources || []).map((source) => [source.id, source]));
  let inserted = 0;
  let updated = 0;

  incomingSources.forEach((rawSource) => {
    const normalized = normalizeSource(rawSource);
    validateSource(normalized);

    if (sourceMap.has(normalized.id)) {
      updated += 1;
    } else {
      inserted += 1;
    }
    sourceMap.set(normalized.id, normalized);
  });

  const next = {
    version: 1,
    updated_at: new Date().toISOString(),
    sources: Array.from(sourceMap.values()).sort((a, b) => a.id.localeCompare(b.id))
  };

  fs.mkdirSync(path.dirname(manifestPath), { recursive: true });
  fs.writeFileSync(manifestPath, `${JSON.stringify(next, null, 2)}\n`, 'utf8');

  return {
    manifestPath,
    inserted,
    updated,
    total: next.sources.length,
    updated_at: next.updated_at
  };
}

module.exports = {
  ingestSources,
  loadManifest
};
