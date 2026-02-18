'use strict';

/**
 * memory-lancedb — Public API
 *
 * Example:
 *   const { MemoryStore, loadMemoryConfig, createEmbedder } = require('./modules/memory-lancedb');
 *   const cfg = loadMemoryConfig();
 *   const store = new MemoryStore(cfg, createEmbedder(cfg));
 *   await store.open();
 *   await store.remember({ text: '...', source: 'dali', tags: ['trading'] });
 *   const hits = await store.recall('bitcoin sentiment', { k: 5 });
 *   await store.close();
 */

const { loadMemoryConfig } = require('./config');
const { createEmbedder, createNullEmbedder, MINIMAX_DIMS, OLLAMA_DIMS_MAP, NULL_DIMS } = require('./embedder');
const { MemoryStore } = require('./store');

module.exports = {
  // Core
  MemoryStore,
  loadMemoryConfig,
  createEmbedder,
  // Utilities
  createNullEmbedder,
  // Constants
  MINIMAX_DIMS,
  OLLAMA_DIMS_MAP,
  NULL_DIMS
};
