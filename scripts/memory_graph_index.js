#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { createMemoryGraphStore } = require('../sys/memory_graph');

function listCandidateFiles(projectRoot) {
  const candidates = [
    'AGENTS.md',
    'MEMORY.md',
    'USER.md',
    'HEARTBEAT.md',
    'SELF_IMPROVEMENT_CONSTITUTION.md'
  ];

  const memoryDir = path.join(projectRoot, 'memory');
  if (fs.existsSync(memoryDir)) {
    fs.readdirSync(memoryDir)
      .filter((entry) => entry.endsWith('.md'))
      .forEach((entry) => candidates.push(path.join('memory', entry)));
  }

  return Array.from(new Set(candidates))
    .map((relativePath) => path.join(projectRoot, relativePath))
    .filter((absolutePath) => fs.existsSync(absolutePath));
}

function main() {
  const projectRoot = process.cwd();
  const store = createMemoryGraphStore();
  const files = listCandidateFiles(projectRoot);

  files.forEach((absolutePath) => {
    const fileNode = store.resolveFileNode(absolutePath);
    const conceptId = `concept:${path.basename(absolutePath, '.md').toLowerCase()}`;

    store.upsertNode({
      '@id': conceptId,
      '@type': 'Concept',
      title: path.basename(absolutePath, '.md'),
      tags: ['concept']
    });

    store.addRelation(fileNode['@id'], conceptId, 'is-about');
  });

  const graph = store.exportGraph();
  console.log(
    JSON.stringify(
      {
        indexedFiles: files.length,
        graphEntries: graph['@graph'].length,
        storagePath: store.storagePath
      },
      null,
      2
    )
  );
}

main();
