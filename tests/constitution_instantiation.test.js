const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');

const {
  loadConstitutionSources,
  buildConstitutionBlock,
  buildConstitutionAuditRecord,
  appendConstitutionAudit,
  sha256
} = require('../core/constitution_instantiation');

const FIXTURE_DIR = path.join(__dirname, 'fixtures', 'constitution');
const SOURCE_PATH = path.join(FIXTURE_DIR, 'constitution_source.md');
const SUPPORTING_PATHS = [
  path.join(FIXTURE_DIR, 'supporting_governance.md'),
  path.join(FIXTURE_DIR, 'supporting_agents.md')
];
const KNOWN_TEXT_SNIPPET = 'Self-improvement occurs only via explicit, versioned changes';

async function runTest(name, fn) {
  try {
    await fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    console.error(`  ${error.message}`);
    throw error;
  }
}

async function testDeterministicTruncationAndHash() {
  const first = loadConstitutionSources({
    sourcePath: SOURCE_PATH,
    supportingPaths: SUPPORTING_PATHS,
    maxChars: 220
  });
  const second = loadConstitutionSources({
    sourcePath: SOURCE_PATH,
    supportingPaths: SUPPORTING_PATHS,
    maxChars: 220
  });

  assert.strictEqual(first.text, second.text, 'constitution text must be deterministic');
  assert.strictEqual(first.sha256, second.sha256, 'constitution hash must be deterministic');
  assert.ok(first.truncated, 'expected truncation with tight cap');
  assert.ok(first.text.includes('[TRUNCATED]'), 'expected deterministic truncation marker');
  assert.strictEqual(first.approxChars, first.text.length);
  assert.strictEqual(first.sha256, sha256(first.text));

  const block = buildConstitutionBlock(first);
  assert.ok(block.includes('[CONSTITUTION_BEGIN sha256='));
  assert.ok(block.includes('[CONSTITUTION_END]'));
}

async function testAuditContainsOnlyMetadata() {
  const snapshot = loadConstitutionSources({
    sourcePath: SOURCE_PATH,
    supportingPaths: SUPPORTING_PATHS,
    maxChars: 8000
  });

  const record = buildConstitutionAuditRecord({
    phase: 'constitution_instantiated',
    runId: 'run_fixture',
    constitution: snapshot
  });

  const serialized = JSON.stringify(record);
  assert.ok(!serialized.includes(KNOWN_TEXT_SNIPPET), 'audit must not contain constitution plaintext');

  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'constitution-audit-'));
  appendConstitutionAudit(record, { rootDir: tempRoot });
  const auditPath = path.join(tempRoot, 'logs', 'constitution_audit.jsonl');
  const fileText = fs.readFileSync(auditPath, 'utf8');

  assert.ok(fileText.includes('constitution_instantiated'));
  assert.ok(!fileText.includes(KNOWN_TEXT_SNIPPET));
}

async function main() {
  await runTest('deterministic truncation and hash', testDeterministicTruncationAndHash);
  await runTest('audit payload excludes constitution text', testAuditContainsOnlyMetadata);
}

main().catch(() => process.exit(1));
