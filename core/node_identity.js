'use strict';

const fs = require('node:fs');
const path = require('node:path');

const SYSTEM_MAP_PATH = path.resolve(__dirname, '..', 'workspace', 'policy', 'system_map.json');

function loadSystemMap(systemMapPath = SYSTEM_MAP_PATH) {
  const raw = fs.readFileSync(systemMapPath, 'utf8');
  const parsed = JSON.parse(raw);
  if (!parsed || typeof parsed !== 'object' || !parsed.nodes || typeof parsed.nodes !== 'object') {
    throw new Error('invalid system_map.json');
  }
  return parsed;
}

function normalizeNodeId(input, systemMap = loadSystemMap()) {
  const defaultNodeId = String(systemMap.default_node_id || 'dali');
  if (input === undefined || input === null || String(input).trim() === '') {
    return defaultNodeId;
  }

  const needle = String(input).trim().toLowerCase();
  for (const [nodeId, nodeCfg] of Object.entries(systemMap.nodes)) {
    const aliases = Array.isArray(nodeCfg.aliases) ? nodeCfg.aliases : [nodeId];
    for (const alias of aliases) {
      if (String(alias).trim().toLowerCase() === needle) {
        return nodeId;
      }
    }
  }
  return defaultNodeId;
}

function resolveNodeRecord(nodeIdOrAlias, systemMap = loadSystemMap()) {
  const nodeId = normalizeNodeId(nodeIdOrAlias, systemMap);
  const nodeCfg = systemMap.nodes[nodeId];
  return {
    node_id: nodeId,
    workspace_root: nodeCfg.workspace_root,
    memory_root: nodeCfg.memory_root
  };
}

module.exports = {
  SYSTEM_MAP_PATH,
  loadSystemMap,
  normalizeNodeId,
  resolveNodeRecord
};
