'use strict';

/**
 * memory-lancedb — Embedders
 *
 * Each embedder exposes:
 *   embedder.dims        {number}  — vector dimension
 *   embedder.embed(texts) → Promise<Float32Array[]>
 *
 * Embedder selection (auto mode): minimax > ollama > null
 */

const https = require('node:https');
const http = require('node:http');

// ── helpers ──────────────────────────────────────────────────────────────────

function jsonPost(urlStr, body, headers) {
  return new Promise((resolve, reject) => {
    const url = new URL(urlStr);
    const isHttps = url.protocol === 'https:';
    const mod = isHttps ? https : http;
    const payload = JSON.stringify(body);

    const req = mod.request(
      {
        hostname: url.hostname,
        port: url.port || (isHttps ? 443 : 80),
        path: url.pathname + (url.search || ''),
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(payload),
          ...headers
        }
      },
      (res) => {
        const chunks = [];
        res.on('data', (c) => chunks.push(c));
        res.on('end', () => {
          const text = Buffer.concat(chunks).toString('utf8');
          if (res.statusCode >= 300) {
            return reject(new Error(`HTTP ${res.statusCode}: ${text.slice(0, 200)}`));
          }
          try {
            resolve(JSON.parse(text));
          } catch {
            reject(new Error(`Invalid JSON response: ${text.slice(0, 200)}`));
          }
        });
      }
    );
    req.on('error', reject);
    req.write(payload);
    req.end();
  });
}

function toFloat32(arr) {
  return arr instanceof Float32Array ? arr : new Float32Array(arr);
}

// ── MiniMax embedder ──────────────────────────────────────────────────────────

const MINIMAX_DIMS = 1536;

function createMinimaxEmbedder(cfg) {
  const { apiKey, baseUrl, model } = cfg.minimax;

  async function embed(texts) {
    const body = { model, input: texts };
    const headers = apiKey ? { Authorization: `Bearer ${apiKey}` } : {};
    const res = await jsonPost(`${baseUrl}/embeddings`, body, headers);

    if (!res.data || !Array.isArray(res.data)) {
      throw new Error(`MiniMax embeddings: unexpected response shape`);
    }
    return res.data.map((item) => toFloat32(item.embedding));
  }

  return { name: 'minimax', dims: MINIMAX_DIMS, embed };
}

// ── Ollama embedder ───────────────────────────────────────────────────────────

const OLLAMA_DIMS_MAP = {
  'nomic-embed-text': 768,
  'mxbai-embed-large': 1024,
  'all-minilm': 384
};

function createOllamaEmbedder(cfg) {
  const { host, model } = cfg.ollama;
  const dims = OLLAMA_DIMS_MAP[model] || 768;

  async function embed(texts) {
    const results = [];
    for (const text of texts) {
      const res = await jsonPost(`${host}/api/embed`, { model, input: text }, {});
      const vec = res.embeddings?.[0] ?? res.embedding;
      if (!vec) throw new Error(`Ollama embed: no embedding in response for model ${model}`);
      results.push(toFloat32(vec));
    }
    return results;
  }

  return { name: 'ollama', dims, embed };
}

// ── Null embedder (for tests) ─────────────────────────────────────────────────

const NULL_DIMS = 4;

function createNullEmbedder() {
  async function embed(texts) {
    return texts.map(() => new Float32Array(NULL_DIMS).fill(0));
  }
  return { name: 'null', dims: NULL_DIMS, embed };
}

// ── Factory ───────────────────────────────────────────────────────────────────

/**
 * Create an embedder from config.
 * Respects MEMORY_EMBEDDER env var; auto-selects based on available keys.
 *
 * @param {object} cfg - from loadMemoryConfig()
 * @returns {{ name: string, dims: number, embed: (texts: string[]) => Promise<Float32Array[]> }}
 */
function createEmbedder(cfg) {
  const mode = cfg.embedder;

  if (mode === 'null') return createNullEmbedder();
  if (mode === 'minimax') return createMinimaxEmbedder(cfg);
  if (mode === 'ollama') return createOllamaEmbedder(cfg);

  // auto: minimax first (if key present), then ollama, then null
  if (mode === 'auto') {
    if (cfg.minimax.apiKey) return createMinimaxEmbedder(cfg);
    return createOllamaEmbedder(cfg);
  }

  throw new Error(`Unknown embedder: ${mode}. Use auto | minimax | ollama | null`);
}

module.exports = { createEmbedder, createNullEmbedder, MINIMAX_DIMS, OLLAMA_DIMS_MAP, NULL_DIMS };
