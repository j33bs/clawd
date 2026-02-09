const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { createMemoryGraphStore } = require('../sys/memory_graph');

function run(name, fn) {
  try {
    fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    console.error(error.message);
    process.exit(1);
  }
}

function withSeedGraph() {
  const fixturePath = path.join(__dirname, 'fixtures', 'sys_graph', 'seed_graph.jsonld');
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sys-graph-test-'));
  const storagePath = path.join(tmpDir, 'memory_graph.jsonld');
  fs.copyFileSync(fixturePath, storagePath);
  return createMemoryGraphStore({ storagePath });
}

run('upsertNode creates and updates nodes', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sys-graph-upsert-'));
  const store = createMemoryGraphStore({ storagePath: path.join(tmpDir, 'graph.jsonld') });

  const first = store.upsertNode({
    '@id': 'concept:test',
    '@type': 'Concept',
    title: 'Test',
    tags: ['alpha']
  });

  const second = store.upsertNode({
    '@id': 'concept:test',
    title: 'Test Updated',
    tags: ['alpha', 'beta']
  });

  assert.strictEqual(first['@id'], 'concept:test');
  assert.strictEqual(second.title, 'Test Updated');
  assert.deepStrictEqual(second.tags, ['alpha', 'beta']);
});

run('addRelation and fetchRelated traverses bidirectionally', () => {
  const store = withSeedGraph();
  const result = store.fetchRelated('breathwork', 2);

  const nodeIds = result.nodes.map((node) => node['@id']);
  assert.ok(nodeIds.includes('concept:breathwork'));
  assert.ok(nodeIds.includes('concept:coherence'));
  assert.ok(nodeIds.includes('file:/tmp/breath-note.md'));
  assert.ok(result.relations.length >= 2);
});

run('resolveFileNode maps path to file node id', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sys-graph-file-'));
  const store = createMemoryGraphStore({ storagePath: path.join(tmpDir, 'graph.jsonld') });
  const targetPath = path.join(tmpDir, 'MEMORY.md');

  const node = store.resolveFileNode(targetPath);
  assert.ok(node['@id'].startsWith('file:'));
  assert.strictEqual(node.path, targetPath);
});
