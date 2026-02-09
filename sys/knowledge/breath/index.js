'use strict';

const path = require('node:path');
const { loadManifest } = require('./ingest');

function defaultManifestPath() {
  return path.join(process.cwd(), 'sys', 'knowledge', 'breath', 'evidence', 'manifest.json');
}

function summary(options = {}) {
  const manifestPath = options.manifestPath || defaultManifestPath();
  const manifest = loadManifest(manifestPath);
  const sources = Array.isArray(manifest.sources) ? manifest.sources : [];

  if (sources.length === 0) {
    return {
      status: 'no_ingested_sources',
      message:
        'No ingested sources. Run scripts/breath_ingest.js --source-manifest <path> to register local evidence.',
      last_updated: manifest.updated_at || null,
      items: []
    };
  }

  const items = [];
  sources.forEach((source) => {
    const claims = Array.isArray(source.claims) ? source.claims : [];
    if (claims.length === 0) {
      items.push({
        evidence_id: source.id,
        claim: source.notes || `Source ${source.id} ingested with no claim text.`
      });
      return;
    }

    claims.forEach((claim) => {
      items.push({
        evidence_id: source.id,
        claim
      });
    });
  });

  return {
    status: 'ok',
    message: `Summary generated from ${sources.length} ingested local source(s).`,
    last_updated: manifest.updated_at || null,
    items
  };
}

module.exports = {
  summary
};
