#!/usr/bin/env node
'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { parseAddedLegacyMentions, lintLegacyNames } = require('../scripts/lint_legacy_node_names');

function test(name, fn) {
  try {
    fn();
    console.log('PASS ' + name);
  } catch (error) {
    console.error('FAIL ' + name + ': ' + error.message);
    process.exitCode = 1;
  }
}

test('parseAddedLegacyMentions finds newly added System-1 references', function () {
  const patch = [
    'diff --git a/docs/x.md b/docs/x.md',
    '+++ b/docs/x.md',
    '+This is System-1 legacy text.',
    '+No issue here.'
  ].join('\n');
  const hits = parseAddedLegacyMentions(patch);
  assert.equal(hits.length, 1);
  assert.equal(hits[0].file, 'docs/x.md');
});

test('lintLegacyNames ignores files with legacy header notice', function () {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'legacy-lint-'));
  const prev = process.cwd();
  try {
    process.chdir(tempDir);
    fs.mkdirSync('docs', { recursive: true });
    fs.writeFileSync('docs/x.md', 'Legacy Node Name Notice:\nSystem-2 allowed here.\n', 'utf8');
    const patch = ['+++ b/docs/x.md', '+System-2 fallback'].join('\n');
    const violations = lintLegacyNames(patch);
    assert.equal(violations.length, 0);
  } finally {
    process.chdir(prev);
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});
