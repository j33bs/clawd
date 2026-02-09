const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const {
  readLegacyMemoryFiles,
  syncLegacyMemoryToGraph,
  renderLegacyBriefCompat
} = require('../sys/adapters/legacy_bridge');
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

run('readLegacyMemoryFiles discovers canonical markdown files', () => {
  const entries = readLegacyMemoryFiles({ projectRoot: process.cwd() });
  assert.ok(entries.length >= 3);
  assert.ok(entries.some((entry) => entry.name === 'AGENTS.md'));
});

run('syncLegacyMemoryToGraph populates file and concept nodes', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'legacy-graph-'));
  const graphStore = createMemoryGraphStore({ storagePath: path.join(tmpDir, 'graph.jsonld') });
  const result = syncLegacyMemoryToGraph({ projectRoot: process.cwd(), graphStore });
  assert.ok(result.synced >= 3);

  const exported = graphStore.exportGraph();
  const hasRelation = exported['@graph'].some((entry) => entry['@type'] === 'Relation');
  assert.ok(hasRelation);
});

run('renderLegacyBriefCompat preserves legacy behavior when disabled', () => {
  const legacy = renderLegacyBriefCompat({ enabled: false, data: { summary: 'legacy summary' } });
  assert.strictEqual(legacy.format, 'markdown');
  assert.strictEqual(legacy.output, 'legacy summary');

  const modern = renderLegacyBriefCompat({
    enabled: true,
    data: {
      title: 'Compat Brief',
      date: '2026-02-09',
      summary: 'Bridge active',
      highlights: { first: 'A', second: 'B' },
      notes: 'ok'
    },
    templatesDir: path.join(process.cwd(), 'sys', 'templates')
  });
  assert.strictEqual(modern.format, 'html');
  assert.ok(modern.output.includes('<h1>Compat Brief</h1>'));
});
