'use strict';

const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

function pass(name) {
  console.log(`PASS ${name}`);
}

function main() {
  const repoRoot = path.resolve(__dirname, '..');
  const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'audit-capsule-'));

  const verifyDir = path.join(tmpRoot, 'notes', 'verification');
  const templatesDir = path.join(verifyDir, 'templates');
  fs.mkdirSync(templatesDir, { recursive: true });

  fs.copyFileSync(
    path.join(repoRoot, 'notes', 'verification', 'templates', 'change_capsule.md.template'),
    path.join(templatesDir, 'change_capsule.md.template')
  );
  fs.copyFileSync(
    path.join(repoRoot, 'notes', 'verification', 'templates', 'change_capsule.json.template'),
    path.join(templatesDir, 'change_capsule.json.template')
  );

  const scriptPath = path.join(repoRoot, 'scripts', 'audit_capsule_new.mjs');

  const firstOut = execFileSync('node', [scriptPath, '--slug', 'audit-layer', '--date', '2026-02-09'], {
    cwd: tmpRoot,
    encoding: 'utf8'
  });
  assert.ok(firstOut.includes('OPERATOR_CONTRACT_START'));

  const md1 = path.join(verifyDir, '2026-02-09-change-capsule-audit-layer.md');
  const json1 = path.join(verifyDir, '2026-02-09-change-capsule-audit-layer.json');
  assert.ok(fs.existsSync(md1));
  assert.ok(fs.existsSync(json1));

  const mdText = fs.readFileSync(md1, 'utf8');
  for (const section of ['## intent', '## design brief', '## evidence', '## tests', '## rollback', '## risk', '## kill-switch', '## post-mortem']) {
    assert.ok(mdText.includes(section), `missing markdown section ${section}`);
  }

  const jsonText = fs.readFileSync(json1, 'utf8');
  const data = JSON.parse(jsonText);
  for (const key of ['intent', 'designBrief', 'evidence', 'tests', 'rollback', 'risk', 'killSwitch', 'postMortem']) {
    assert.ok(Object.prototype.hasOwnProperty.call(data, key), `missing json key ${key}`);
  }
  pass('capsule generator creates required fields');

  execFileSync('node', [scriptPath, '--slug', 'audit-layer', '--date', '2026-02-09'], {
    cwd: tmpRoot,
    encoding: 'utf8'
  });

  const md2 = path.join(verifyDir, '2026-02-09-change-capsule-audit-layera.md');
  const json2 = path.join(verifyDir, '2026-02-09-change-capsule-audit-layera.json');
  assert.ok(fs.existsSync(md2));
  assert.ok(fs.existsSync(json2));
  pass('capsule generator uses collision-safe suffix');
}

main();
