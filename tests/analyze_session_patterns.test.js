'use strict';

const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const {
  analyzeSessions,
  analyzeSessionsConcurrent,
  renderReport
} = require('../scripts/analyze_session_patterns');

function testPatternAggregation() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'pattern-scan-'));
  const memoryDir = path.join(root, 'workspace', 'memory');
  fs.mkdirSync(memoryDir, { recursive: true });

  fs.writeFileSync(
    path.join(memoryDir, '2026-02-10.md'),
    [
      'all models failed after provider escalation',
      'cooldown retry loop detected in classifier',
      'fallback local auth unauthorized',
      'normal note'
    ].join('\n'),
    'utf8'
  );

  const result = analyzeSessions({ memoryDir });
  const byId = new Map(result.findings.map((f) => [f.id, f]));
  assert.strictEqual(byId.get('all_models_failed').total, 1);
  assert.strictEqual(byId.get('cooldown_loop').total, 1);
  assert.strictEqual(byId.get('local_fallback_auth_error').total, 1);

  const report = renderReport({ dateKey: '2026-02-17', scannedFiles: result.scannedFiles, findings: result.findings });
  assert.ok(report.includes('session-patterns') === false);
  assert.ok(report.includes('all_models_failed'));
  console.log('PASS analyze_session_patterns aggregates recurring inefficiency patterns');
}

testPatternAggregation();

async function testConcurrentParity() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'pattern-scan-workers-'));
  const memoryDir = path.join(root, 'workspace', 'memory');
  fs.mkdirSync(memoryDir, { recursive: true });
  fs.writeFileSync(path.join(memoryDir, '2026-02-11.md'), 'all models failed\\nnormal note\\n', 'utf8');
  fs.writeFileSync(path.join(memoryDir, '2026-02-12.md'), 'cooldown retry loop\\n', 'utf8');
  const syncResult = analyzeSessions({ memoryDir });
  const concurrentResult = await analyzeSessionsConcurrent({ memoryDir, workers: 2 });
  assert.deepStrictEqual(concurrentResult, syncResult);
  console.log('PASS analyze_session_patterns concurrent parity');
}

testConcurrentParity().catch((err) => {
  console.error(err);
  process.exit(1);
});
