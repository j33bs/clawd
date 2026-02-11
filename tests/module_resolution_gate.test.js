'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { summarize } = require('../scripts/module_resolution_gate');

function writeFile(filePath, content) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content, 'utf8');
}

function run(name, fn) {
  try {
    fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}: ${error.message}`);
    process.exitCode = 1;
  }
}

run('returns zero findings when relative require resolves', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'module-gate-ok-'));
  const okSpec = './b';
  writeFile(path.join(root, 'src', 'a.js'), `const b = require('${okSpec}'); module.exports = b;\n`);
  writeFile(path.join(root, 'src', 'b.js'), "module.exports = 1;\n");

  const result = summarize(root);
  assert.equal(result.findings_count, 0);
  assert.deepEqual(result.findings, []);
});

run('reports finding when relative require target is missing', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'module-gate-missing-'));
  const missingSpec = './missing';
  writeFile(path.join(root, 'src', 'a.js'), `const x = require('${missingSpec}'); module.exports = x;\n`);

  const result = summarize(root);
  assert.equal(result.findings_count, 1);
  assert.equal(result.findings[0].file, 'src/a.js');
  assert.equal(result.findings[0].specifier, './missing');
});

console.log('module_resolution_gate tests complete');
