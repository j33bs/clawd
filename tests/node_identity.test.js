#!/usr/bin/env node
'use strict';

const assert = require('node:assert/strict');
const { loadSystemMap, normalizeNodeId, resolveNodeRecord } = require('../core/node_identity');

function test(name, fn) {
  try {
    fn();
    console.log('PASS ' + name);
  } catch (error) {
    console.error('FAIL ' + name + ': ' + error.message);
    process.exitCode = 1;
  }
}

test('loads system map with expected defaults', function () {
  const map = loadSystemMap();
  assert.equal(map.default_node_id, 'dali');
  assert.ok(map.nodes.dali);
  assert.ok(map.nodes.c_lawd);
});

test('normalizes system1/system-1 aliases to dali', function () {
  assert.equal(normalizeNodeId('system1'), 'dali');
  assert.equal(normalizeNodeId('system-1'), 'dali');
});

test('normalizes system2/system-2 aliases to c_lawd', function () {
  assert.equal(normalizeNodeId('system2'), 'c_lawd');
  assert.equal(normalizeNodeId('system-2'), 'c_lawd');
});

test('resolves workspace and memory roots from alias', function () {
  const rec = resolveNodeRecord('system2');
  assert.equal(rec.node_id, 'c_lawd');
  assert.equal(rec.workspace_root, 'nodes/c_lawd');
  assert.equal(rec.memory_root, 'nodes/c_lawd');
});
