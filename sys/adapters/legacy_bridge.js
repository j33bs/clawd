'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { render } = require('../render');

const LEGACY_MEMORY_FILES = [
  'AGENTS.md',
  'MEMORY.md',
  'USER.md',
  'HEARTBEAT.md',
  'SELF_IMPROVEMENT_CONSTITUTION.md'
];

function readLegacyMemoryFiles(options = {}) {
  const projectRoot = options.projectRoot || process.cwd();
  const entries = [];

  LEGACY_MEMORY_FILES.forEach((relativePath) => {
    const absolutePath = path.join(projectRoot, relativePath);
    if (!fs.existsSync(absolutePath)) {
      return;
    }

    const content = fs.readFileSync(absolutePath, 'utf8');
    entries.push({
      path: absolutePath,
      name: relativePath,
      chars: content.length
    });
  });

  return entries;
}

function syncLegacyMemoryToGraph(options = {}) {
  const graphStore = options.graphStore;
  if (!graphStore) {
    throw new Error('syncLegacyMemoryToGraph requires graphStore');
  }

  const projectRoot = options.projectRoot || process.cwd();
  const entries = readLegacyMemoryFiles({ projectRoot });

  entries.forEach((entry) => {
    const fileNode = graphStore.upsertNode({
      '@id': `file:${entry.path}`,
      '@type': 'MemoryFile',
      title: entry.name,
      path: entry.path,
      tags: ['legacy-memory']
    });

    const conceptId = `concept:${entry.name.replace(/\.md$/i, '').toLowerCase()}`;
    graphStore.upsertNode({
      '@id': conceptId,
      '@type': 'Concept',
      title: entry.name.replace(/\.md$/i, ''),
      tags: ['legacy-concept']
    });

    graphStore.addRelation(fileNode['@id'], conceptId, 'is-about');
  });

  return {
    synced: entries.length,
    entries
  };
}

function renderLegacyBriefCompat(options = {}) {
  const enabled = Boolean(options.enabled);
  const data = options.data || {};

  if (!enabled) {
    return {
      format: 'markdown',
      output: String(data.markdown || data.summary || 'legacy brief mode (no sys renderer)')
    };
  }

  return render({
    template: options.template || 'brief',
    format: options.format || 'html',
    data,
    templatesDir: options.templatesDir
  });
}

module.exports = {
  LEGACY_MEMORY_FILES,
  readLegacyMemoryFiles,
  syncLegacyMemoryToGraph,
  renderLegacyBriefCompat
};
