'use strict';

/**
 * memory-lancedb — Configuration
 *
 * All values sourced from environment variables with conservative defaults.
 * Embedder priority: minimax (if key present) > ollama > null.
 *
 * Env vars:
 *   MEMORY_LANCEDB_PATH       — local directory for the LanceDB files (default: .tmp/memory-lancedb)
 *   MEMORY_LANCEDB_TABLE      — table name (default: memories)
 *   MEMORY_EMBEDDER           — auto | minimax | ollama | null (default: auto)
 *   MEMORY_MINIMAX_BASE_URL   — MiniMax API base (default: https://api.minimax.chat/v1)
 *   MEMORY_MINIMAX_MODEL      — embedding model name (default: embo-01)
 *   MEMORY_OLLAMA_HOST        — Ollama base URL (default: http://localhost:11434)
 *   MEMORY_OLLAMA_MODEL       — Ollama model (default: nomic-embed-text)
 *   MEMORY_RECALL_LIMIT       — default k for recall (default: 5)
 */

function loadMemoryConfig(env) {
  const e = env || process.env;

  // Resolve MiniMax API key from project convention or generic fallback
  const minimaxKey =
    e.OPENCLAW_MINIMAX_PORTAL_API_KEY ||
    e.MINIMAX_API_KEY ||
    '';

  const embedder = (e.MEMORY_EMBEDDER || 'auto').toLowerCase();

  return {
    lancedb: {
      path: e.MEMORY_LANCEDB_PATH || '.tmp/memory-lancedb',
      table: e.MEMORY_LANCEDB_TABLE || 'memories'
    },
    embedder,
    minimax: {
      apiKey: minimaxKey,
      baseUrl: e.MEMORY_MINIMAX_BASE_URL || 'https://api.minimax.chat/v1',
      model: e.MEMORY_MINIMAX_MODEL || 'embo-01'
    },
    ollama: {
      host: e.MEMORY_OLLAMA_HOST || 'http://localhost:11434',
      model: e.MEMORY_OLLAMA_MODEL || 'nomic-embed-text'
    },
    recallLimit: Number(e.MEMORY_RECALL_LIMIT || 5)
  };
}

module.exports = { loadMemoryConfig };
