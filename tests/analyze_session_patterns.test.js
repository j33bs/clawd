'use strict';

const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const {
  analyzeSessions,
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
