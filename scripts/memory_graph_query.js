#!/usr/bin/env node
'use strict';

const { createMemoryGraphStore } = require('../sys/memory_graph');

function main() {
  const term = process.argv[2] || '';
  const hops = Number(process.argv[3] || 1);

  if (!term) {
    console.error('Usage: node scripts/memory_graph_query.js <termOrId> [hops]');
    process.exit(1);
  }

  const store = createMemoryGraphStore();
  const result = store.fetchRelated(term, hops);
  console.log(JSON.stringify(result, null, 2));
}

main();
