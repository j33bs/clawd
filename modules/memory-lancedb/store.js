'use strict';

/**
 * memory-lancedb — MemoryStore
 *
 * Wraps LanceDB to provide semantic memory for agents.
 *
 * Usage:
 *   const store = new MemoryStore(config, embedder);
 *   await store.open();
 *   await store.remember({ text, source, tags, metadata });
 *   const hits = await store.recall('query text', { k: 5 });
 *   await store.close();
 */

const crypto = require('node:crypto');
const fs = require('node:fs');
const lancedb = require('@lancedb/lancedb');

class MemoryStore {
  /**
   * @param {object} cfg - from loadMemoryConfig()
   * @param {object} embedder - from createEmbedder(cfg)
   */
  constructor(cfg, embedder) {
    this._cfg = cfg;
    this._embedder = embedder;
    this._db = null;
    this._table = null;
  }

  /**
   * Open (or create) the LanceDB database and memories table.
   * Must be called before remember() or recall().
   */
  async open() {
    const { path: dbPath, table: tableName } = this._cfg.lancedb;

    fs.mkdirSync(dbPath, { recursive: true });
    this._db = await lancedb.connect(dbPath);

    const tableNames = await this._db.tableNames();
    if (tableNames.includes(tableName)) {
      this._table = await this._db.openTable(tableName);
    }
    // If the table doesn't exist yet, defer creation until first remember()
  }

  /**
   * Store a memory entry.
   *
   * @param {object} entry
   * @param {string} entry.text      - the memory text
   * @param {string} [entry.source]  - who created it (dali, c_lawd, user, …)
   * @param {string[]} [entry.tags]  - optional tags
   * @param {object} [entry.metadata] - arbitrary JSON-serializable data
   */
  async remember(entry) {
    if (!this._db) throw new Error('MemoryStore not open — call open() first');

    const { text, source = 'unknown', tags = [], metadata = {} } = entry;
    if (!text || typeof text !== 'string') throw new Error('entry.text is required');

    const [vector] = await this._embedder.embed([text]);
    const record = {
      id: crypto.randomUUID(),
      ts_utc: new Date().toISOString(),
      text,
      source,
      tags: JSON.stringify(Array.isArray(tags) ? tags.map(String) : []),
      metadata: JSON.stringify(metadata),
      vector: Array.from(vector)
    };

    const tableName = this._cfg.lancedb.table;
    if (!this._table) {
      this._table = await this._db.createTable(tableName, [record]);
    } else {
      await this._table.add([record]);
    }
  }

  /**
   * Recall semantically similar memories.
   *
   * @param {string} queryText
   * @param {object} [opts]
   * @param {number} [opts.k]         - number of results (default from config)
   * @param {string} [opts.source]    - filter by source
   * @returns {Promise<Array<{ id, ts_utc, text, source, tags, metadata, score }>>}
   */
  async recall(queryText, opts = {}) {
    if (!this._db) throw new Error('MemoryStore not open — call open() first');
    if (!this._table) return [];

    const k = opts.k ?? this._cfg.recallLimit;
    const [vector] = await this._embedder.embed([queryText]);

    let q = this._table.search(Array.from(vector)).limit(k);
    if (opts.source) {
      if (!/^[a-zA-Z0-9_.\-@]+$/.test(opts.source)) {
        throw new Error(`invalid source filter value: ${opts.source}`);
      }
      q = q.where(`source = '${opts.source}'`);
    }

    const rows = await q.toArray();
    return rows.map((r) => ({
      id: r.id,
      ts_utc: r.ts_utc,
      text: r.text,
      source: r.source,
      tags: _safeParse(r.tags, []),
      metadata: _safeParse(r.metadata, {}),
      score: r._distance
    }));
  }

  /** Flush pending writes. LanceDB is currently synchronous-on-write, so this is a no-op. */
  async close() {
    this._table = null;
    this._db = null;
  }
}

function _safeParse(str, fallback) {
  try {
    return JSON.parse(str);
  } catch {
    return fallback;
  }
}

module.exports = { MemoryStore };
