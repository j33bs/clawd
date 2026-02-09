'use strict';

const fs = require('node:fs');
const path = require('node:path');

const RELATION_TYPES = new Set(['is-about', 'extends', 'learned-from', 'supersedes']);
const DEFAULT_GRAPH = {
  '@context': 'https://schema.org',
  '@graph': []
};

function ensureDir(targetPath) {
  fs.mkdirSync(path.dirname(targetPath), { recursive: true });
}

function deepClone(value) {
  return JSON.parse(JSON.stringify(value));
}

function nowIso() {
  return new Date().toISOString();
}

function normalizeTags(tags) {
  if (!Array.isArray(tags)) {
    return [];
  }
  return Array.from(
    new Set(
      tags
        .map((tag) => String(tag || '').trim())
        .filter(Boolean)
    )
  );
}

function createDefaultGraph() {
  return deepClone(DEFAULT_GRAPH);
}

function createMemoryGraphStore(options = {}) {
  const storagePath = options.storagePath || path.join(process.cwd(), 'sys', 'state', 'memory_graph.jsonld');

  function loadGraph() {
    if (!fs.existsSync(storagePath)) {
      return createDefaultGraph();
    }

    try {
      const parsed = JSON.parse(fs.readFileSync(storagePath, 'utf8'));
      if (!parsed || typeof parsed !== 'object' || !Array.isArray(parsed['@graph'])) {
        return createDefaultGraph();
      }
      if (!parsed['@context']) {
        parsed['@context'] = 'https://schema.org';
      }
      return parsed;
    } catch (error) {
      return createDefaultGraph();
    }
  }

  function saveGraph(graph) {
    ensureDir(storagePath);
    fs.writeFileSync(storagePath, `${JSON.stringify(graph, null, 2)}\n`, 'utf8');
  }

  function listNodes(graph) {
    return graph['@graph'].filter((entry) => entry['@type'] !== 'Relation');
  }

  function listRelations(graph) {
    return graph['@graph'].filter((entry) => entry['@type'] === 'Relation');
  }

  function findNode(graph, nodeId) {
    return graph['@graph'].find((entry) => entry['@id'] === nodeId && entry['@type'] !== 'Relation');
  }

  function findRelation(graph, from, to, relType) {
    return graph['@graph'].find(
      (entry) =>
        entry['@type'] === 'Relation' &&
        entry.from === from &&
        entry.to === to &&
        entry.rel_type === relType
    );
  }

  function upsertNode(node) {
    if (!node || typeof node !== 'object') {
      throw new Error('upsertNode requires a node object');
    }

    const nodeId = node['@id'] || node.id;
    if (!nodeId) {
      throw new Error('upsertNode requires @id');
    }

    const graph = loadGraph();
    const existing = findNode(graph, nodeId);
    const timestamp = nowIso();

    if (existing) {
      existing['@type'] = node['@type'] || existing['@type'] || 'MemoryFile';
      existing.title = node.title || existing.title || nodeId;
      existing.path = node.path || existing.path || null;
      existing.tags = normalizeTags(node.tags || existing.tags || []);
      existing.updated_at = timestamp;
      saveGraph(graph);
      return deepClone(existing);
    }

    const created = {
      '@id': nodeId,
      '@type': node['@type'] || 'MemoryFile',
      title: node.title || nodeId,
      path: node.path || null,
      tags: normalizeTags(node.tags || []),
      created_at: timestamp,
      updated_at: timestamp
    };

    graph['@graph'].push(created);
    saveGraph(graph);
    return deepClone(created);
  }

  function addRelation(from, to, relType) {
    if (!RELATION_TYPES.has(relType)) {
      throw new Error(`Unsupported relation type: ${relType}`);
    }

    const graph = loadGraph();
    if (!findNode(graph, from)) {
      throw new Error(`Cannot create relation: missing from node ${from}`);
    }
    if (!findNode(graph, to)) {
      throw new Error(`Cannot create relation: missing to node ${to}`);
    }

    const existing = findRelation(graph, from, to, relType);
    if (existing) {
      existing.updated_at = nowIso();
      saveGraph(graph);
      return deepClone(existing);
    }

    const timestamp = nowIso();
    const relation = {
      '@id': `rel:${from}:${relType}:${to}`,
      '@type': 'Relation',
      from,
      to,
      rel_type: relType,
      created_at: timestamp,
      updated_at: timestamp
    };

    graph['@graph'].push(relation);
    saveGraph(graph);
    return deepClone(relation);
  }

  function matchingNodeIds(graph, termOrId) {
    const needle = String(termOrId || '').trim().toLowerCase();
    if (!needle) {
      return [];
    }

    const nodes = listNodes(graph);
    const byId = nodes.filter((node) => String(node['@id']).toLowerCase() === needle).map((node) => node['@id']);
    if (byId.length > 0) {
      return byId;
    }

    return nodes
      .filter((node) => {
        const title = String(node.title || '').toLowerCase();
        const nodePath = String(node.path || '').toLowerCase();
        const tags = normalizeTags(node.tags || []).map((tag) => tag.toLowerCase());
        return title.includes(needle) || nodePath.includes(needle) || tags.some((tag) => tag.includes(needle));
      })
      .map((node) => node['@id']);
  }

  function fetchRelated(termOrId, hops = 1) {
    const graph = loadGraph();
    const hopLimit = Number.isFinite(Number(hops)) ? Math.max(0, Number(hops)) : 1;
    const seedIds = matchingNodeIds(graph, termOrId);
    const relations = listRelations(graph);

    const visited = new Set(seedIds);
    const queue = seedIds.map((id) => ({ id, depth: 0 }));
    const touchedRelations = new Set();

    while (queue.length > 0) {
      const current = queue.shift();
      if (current.depth >= hopLimit) {
        continue;
      }

      relations.forEach((relation) => {
        let neighbor = null;
        if (relation.from === current.id) {
          neighbor = relation.to;
        } else if (relation.to === current.id) {
          neighbor = relation.from;
        }

        if (!neighbor) {
          return;
        }

        touchedRelations.add(relation['@id']);
        if (!visited.has(neighbor)) {
          visited.add(neighbor);
          queue.push({ id: neighbor, depth: current.depth + 1 });
        }
      });
    }

    const nodes = listNodes(graph).filter((node) => visited.has(node['@id']));
    const relationList = relations.filter((relation) => touchedRelations.has(relation['@id']));

    return {
      term: termOrId,
      hops: hopLimit,
      seedIds,
      nodes: deepClone(nodes),
      relations: deepClone(relationList)
    };
  }

  function resolveFileNode(filePath) {
    const resolvedPath = path.resolve(String(filePath || ''));
    return upsertNode({
      '@id': `file:${resolvedPath}`,
      '@type': 'MemoryFile',
      title: path.basename(resolvedPath),
      path: resolvedPath,
      tags: ['memory-file']
    });
  }

  function exportGraph() {
    return deepClone(loadGraph());
  }

  return {
    storagePath,
    upsertNode,
    addRelation,
    fetchRelated,
    resolveFileNode,
    exportGraph,
    RELATION_TYPES: Array.from(RELATION_TYPES)
  };
}

module.exports = {
  createMemoryGraphStore,
  RELATION_TYPES: Array.from(RELATION_TYPES)
};
