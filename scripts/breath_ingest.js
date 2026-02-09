#!/usr/bin/env node
'use strict';

const path = require('node:path');
const { ingestSources } = require('../sys/knowledge/breath/ingest');

function parseArgs(argv) {
  const parsed = {
    sourceManifestPath: null,
    manifestPath: path.join(process.cwd(), 'sys', 'knowledge', 'breath', 'evidence', 'manifest.json')
  };

  argv.forEach((arg, index) => {
    if (arg === '--source-manifest') {
      parsed.sourceManifestPath = argv[index + 1] || null;
    }
    if (arg === '--manifest') {
      parsed.manifestPath = argv[index + 1] || parsed.manifestPath;
    }
  });

  return parsed;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.sourceManifestPath) {
    console.error('Usage: node scripts/breath_ingest.js --source-manifest <path> [--manifest <path>]');
    process.exit(1);
  }

  const result = ingestSources({
    manifestPath: args.manifestPath,
    sourceManifestPath: args.sourceManifestPath
  });

  console.log(JSON.stringify(result, null, 2));
}

main();
