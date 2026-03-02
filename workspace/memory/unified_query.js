'use strict';

const fs = require('node:fs');
const path = require('node:path');

function resolveRepoRoot(startDir) {
  let current = path.resolve(startDir || process.cwd());
  for (let i = 0; i < 8; i += 1) {
    if (fs.existsSync(path.join(current, '.git'))) return current;
    const parent = path.dirname(current);
    if (parent === current) break;
    current = parent;
  }
  return path.resolve(startDir || process.cwd());
}

function toArray(value) {
  return Array.isArray(value) ? value : [];
}

function toTimestampMs(value) {
  if (!value) return null;
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  const ms = Date.parse(String(value));
  return Number.isFinite(ms) ? ms : null;
}

function normalizeItem(raw, sourceId) {
  const item = raw && typeof raw === 'object' ? raw : {};
  return {
    source: String(item.source || sourceId || 'unknown'),
    ts: item.ts || null,
    kind: String(item.kind || 'note'),
    title: String(item.title || ''),
    text: String(item.text || ''),
    refs: toArray(item.refs).map((x) => String(x)).filter(Boolean),
    ...(item.score !== undefined ? { score: Number(item.score) } : {})
  };
}

function makeCorrespondenceStoreAdapter(opts = {}) {
  const id = 'correspondence_store';
  return {
    id,
    async query(params = {}) {
      if (Array.isArray(opts.fixtureItems)) return opts.fixtureItems;
      const fetchImpl = opts.fetchImpl || (typeof fetch === 'function' ? fetch : null); // eslint-disable-line no-undef
      if (!fetchImpl) return [];

      const baseUrl = opts.baseUrl || process.env.CORRESPONDENCE_STORE_BASE_URL || 'http://127.0.0.1:8765';
      const n = Math.max(1, Number(params.window || params.limit || 40));
      const url = `${baseUrl.replace(/\/+$/, '')}/tail?n=${n}`;

      try {
        const response = await fetchImpl(url);
        if (!response || !response.ok) return [];
        const payload = await response.json();
        if (!Array.isArray(payload)) return [];
        return payload.map((row) => ({
          source: id,
          ts: row.created_at || null,
          kind: 'section',
          title: row.title || '',
          text: row.body || '',
          refs: [
            row.canonical_section_number !== undefined ? `canonical:${row.canonical_section_number}` : null
          ].filter(Boolean)
        }));
      } catch (_error) {
        return [];
      }
    }
  };
}

function makeGovernanceLogAdapter(opts = {}) {
  const id = 'governance_log';
  const repoRoot = resolveRepoRoot(opts.repoRoot || process.cwd());
  const logPath = opts.path || path.join(repoRoot, 'workspace', 'governance', 'OPEN_QUESTIONS.md');

  return {
    id,
    async query() {
      if (Array.isArray(opts.fixtureItems)) return opts.fixtureItems;
      if (!fs.existsSync(logPath)) return [];
      const lines = fs.readFileSync(logPath, 'utf8').split('\n');
      const out = [];

      let current = null;
      for (const line of lines) {
        const header = line.match(/^## ([IVXLCDM]+)\.\s+(.+)$/i);
        if (header) {
          if (current) out.push(current);
          const title = String(header[2] || '').trim();
          const dateMatch = title.match(/\b(20\d\d-\d\d-\d\d)\b/);
          current = {
            source: id,
            ts: dateMatch ? `${dateMatch[1]}T00:00:00Z` : null,
            kind: 'governance_section',
            title,
            text: '',
            refs: [`file:${path.relative(repoRoot, logPath)}`]
          };
          continue;
        }
        if (current) current.text += `${line}\n`;
      }
      if (current) out.push(current);
      return out.map((item) => ({ ...item, text: item.text.trim() }));
    }
  };
}

function makeVectorStoreAdapter(opts = {}) {
  const id = 'vector_store';
  const repoRoot = resolveRepoRoot(opts.repoRoot || process.cwd());
  const jsonlPath = opts.path || path.join(repoRoot, 'workspace', 'knowledge_base', 'data', 'entities.jsonl');

  return {
    id,
    async query(params = {}) {
      if (Array.isArray(opts.fixtureItems)) return opts.fixtureItems;
      if (!fs.existsSync(jsonlPath)) return [];
      const rawLines = fs.readFileSync(jsonlPath, 'utf8').split('\n').filter(Boolean);
      const limit = Math.max(1, Number(params.window || params.limit || 50));
      const out = [];
      for (const line of rawLines) {
        let parsed;
        try {
          parsed = JSON.parse(line);
        } catch (_error) {
          continue;
        }
        if (!parsed || typeof parsed !== 'object') continue;
        out.push({
          source: id,
          ts: parsed.created_at || null,
          kind: parsed.entity_type || 'entity',
          title: parsed.name || '',
          text: parsed.content || '',
          refs: [parsed.id ? `entity:${parsed.id}` : null].filter(Boolean)
        });
        if (out.length >= limit) break;
      }
      return out;
    }
  };
}

function createDefaultAdapters(opts = {}) {
  return [
    makeCorrespondenceStoreAdapter(opts.correspondence || {}),
    makeGovernanceLogAdapter(opts.governance || {}),
    makeVectorStoreAdapter(opts.vector || {})
  ];
}

class UnifiedMemoryQuery {
  constructor(opts = {}) {
    this.adapters = Array.isArray(opts.adapters) ? opts.adapters : createDefaultAdapters(opts);
  }

  async query(params = {}) {
    const sourceFilter = Array.isArray(params.sources) && params.sources.length > 0
      ? new Set(params.sources.map((x) => String(x)))
      : null;
    const requestedLimit = Number(params.limit || 20);
    const limit = Number.isFinite(requestedLimit) ? Math.max(1, requestedLimit) : 20;
    const q = String(params.q || '').trim().toLowerCase();
    const tags = Array.isArray(params.tags) ? params.tags.map((x) => String(x).toLowerCase()) : [];

    const collected = [];
    for (const adapter of this.adapters) {
      if (!adapter || typeof adapter.query !== 'function') continue;
      const sourceId = String(adapter.id || 'unknown');
      if (sourceFilter && !sourceFilter.has(sourceId)) continue;
      let rows = [];
      try {
        rows = await adapter.query(params);
      } catch (_error) {
        rows = [];
      }
      for (const row of toArray(rows)) {
        const item = normalizeItem(row, sourceId);
        if (q) {
          const hay = `${item.title}\n${item.text}`.toLowerCase();
          if (!hay.includes(q)) continue;
        }
        if (tags.length > 0) {
          const refsLower = item.refs.map((x) => x.toLowerCase());
          const hasTag = tags.some((tag) => refsLower.some((ref) => ref.includes(tag)));
          if (!hasTag) continue;
        }
        collected.push(item);
      }
    }

    const withSortKeys = collected.map((item, idx) => ({
      item,
      idx,
      tsMs: toTimestampMs(item.ts)
    }));

    withSortKeys.sort((a, b) => {
      if (a.tsMs === null && b.tsMs === null) return a.idx - b.idx;
      if (a.tsMs === null) return 1;
      if (b.tsMs === null) return -1;
      if (a.tsMs === b.tsMs) return a.idx - b.idx;
      return b.tsMs - a.tsMs;
    });

    return withSortKeys.slice(0, limit).map((entry) => entry.item);
  }
}

module.exports = {
  UnifiedMemoryQuery,
  createDefaultAdapters,
  makeCorrespondenceStoreAdapter,
  makeGovernanceLogAdapter,
  makeVectorStoreAdapter
};

// ---------------------------------------------------------------------------
// CLI entry point  (node workspace/memory/unified_query.js --q "search term")
// ---------------------------------------------------------------------------
if (require.main === module) {
  const args = process.argv.slice(2);
  const qIdx = args.indexOf('--q');
  const query = qIdx !== -1 ? args[qIdx + 1] : null;
  const limitIdx = args.indexOf('--limit');
  const limit = limitIdx !== -1 ? parseInt(args[limitIdx + 1], 10) : 10;
  const baseUrl = process.env.CORRESPONDENCE_STORE_BASE_URL || 'http://127.0.0.1:8765';

  if (!query) {
    process.stderr.write('Usage: node workspace/memory/unified_query.js --q <query> [--limit N]\n');
    process.exit(1);
  }

  const umq = new UnifiedMemoryQuery({ adapters: createDefaultAdapters({ baseUrl }) });
  umq.query({ q: query, limit }).then((results) => {
    process.stdout.write(JSON.stringify(results, null, 2) + '\n');
  }).catch((err) => {
    process.stderr.write(String(err) + '\n');
    process.exit(1);
  });
}

