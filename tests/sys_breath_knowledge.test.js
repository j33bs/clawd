const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const breath = require('../sys/knowledge/breath');
const { ingestSources } = require('../sys/knowledge/breath/ingest');

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

run('breath summary returns no_ingested_sources when empty', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sys-breath-empty-'));
  const manifestPath = path.join(tmpDir, 'manifest.json');
  fs.writeFileSync(
    manifestPath,
    JSON.stringify({ version: 1, updated_at: null, sources: [] }, null, 2),
    'utf8'
  );

  const result = breath.summary({ manifestPath });
  assert.strictEqual(result.status, 'no_ingested_sources');
  assert.strictEqual(result.items.length, 0);
});

run('ingest pipeline populates evidence manifest and citations', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sys-breath-ingest-'));
  const manifestPath = path.join(tmpDir, 'manifest.json');
  const sourceManifestPath = path.join(__dirname, 'fixtures', 'breath', 'source_manifest.json');

  const ingestResult = ingestSources({ manifestPath, sourceManifestPath });
  assert.strictEqual(ingestResult.inserted, 1);

  const summary = breath.summary({ manifestPath });
  assert.strictEqual(summary.status, 'ok');
  assert.ok(summary.items.length >= 1);
  assert.ok(summary.items.every((item) => item.evidence_id === 'breath-hrv-2025-01'));
});
