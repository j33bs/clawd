#!/usr/bin/env node
'use strict';

const assert = require('assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { applyRules, buildRules, validateJson } = require('../scripts/redact_audit_evidence');

function test(name, fn) {
  try {
    fn();
    console.log('PASS ' + name);
  } catch (err) {
    console.error('FAIL ' + name + ': ' + err.message);
    process.exitCode = 1;
  }
}

function runCli(args) {
  const scriptPath = path.resolve(__dirname, '..', 'scripts', 'redact_audit_evidence.js');
  return spawnSync(process.execPath, [scriptPath, ...args], { encoding: 'utf8' });
}

// --- Idempotence ---

test('idempotent: applying rules twice yields same result', function () {
  const input = [
    '  "configPath": "/Users/heathyeager/.openclaw/openclaw.json"',
    'snapshot_dir=/Users/heathyeager/clawd/workspace/docs/audits/bar',
    'drwxr-xr-x@ 12 heathyeager  staff   384B Feb 11 23:45 .',
    'just heathyeager in text'
  ].join('\n');
  const rules = buildRules();
  const first = applyRules(input, rules);
  const second = applyRules(first.result, buildRules());
  assert.strictEqual(first.result, second.result, 'second pass should produce no changes');
  const totalSecond = Object.values(second.counts).reduce((a, b) => a + b, 0);
  assert.strictEqual(totalSecond, 0, 'second pass should have zero replacements');
});

// --- JSON validity preserved ---

test('JSON validity preserved after redaction', function () {
  const jsonStr = JSON.stringify({
    configPath: '/Users/heathyeager/.openclaw/openclaw.json',
    outDir: '/Users/heathyeager/clawd/workspace/docs/audits/foo',
    user: 'heathyeager',
    nested: { path: '/Users/heathyeager/clawd/data' }
  }, null, 2);
  assert.ok(validateJson(jsonStr), 'input should be valid JSON');
  const rules = buildRules();
  const { result } = applyRules(jsonStr, rules);
  assert.ok(validateJson(result), 'output should still be valid JSON');
  assert.ok(!result.includes('/Users/'), 'no /Users/ paths should remain');
  assert.ok(!result.includes('heathyeager'), 'no username should remain');
});

// --- No leakage after redaction ---

test('no /Users/ or heathyeager remains after redaction', function () {
  const input = [
    '/Users/heathyeager/clawd/foo',
    '/Users/heathyeager/.openclaw/bar',
    '/Users/heathyeager/other',
    'drwxr-xr-x@  3 heathyeager  staff    96B Feb 11 23:45 ..',
    'owned by heathyeager on this host'
  ].join('\n');
  const rules = buildRules();
  const { result } = applyRules(input, rules);
  assert.ok(!result.includes('/Users/'), 'no /Users/ should remain');
  assert.ok(!result.includes('heathyeager'), 'no heathyeager should remain');
});

// --- Replacement correctness ---

test('repo root path replaced correctly', function () {
  const rules = buildRules();
  const { result } = applyRules('/Users/heathyeager/clawd/workspace/foo', rules);
  assert.strictEqual(result, '{{REPO_ROOT}}/workspace/foo');
});

test('openclaw config path replaced correctly', function () {
  const rules = buildRules();
  const { result } = applyRules('/Users/heathyeager/.openclaw/openclaw.json', rules);
  assert.strictEqual(result, '{{HOME}}/.openclaw/openclaw.json');
});

test('generic home path replaced correctly', function () {
  const rules = buildRules();
  const { result } = applyRules('/Users/heathyeager/clawd_external/modules', rules);
  assert.strictEqual(result, '{{HOME}}/clawd_external/modules');
});

test('ls -la line replaced correctly', function () {
  const rules = buildRules();
  const { result } = applyRules(
    'drwxr-xr-x@ 12 heathyeager  staff   384B Feb 11 23:45 .',
    rules
  );
  assert.ok(result.includes('{{USER}}'), 'owner should be redacted');
  assert.ok(result.includes('{{GROUP}}'), 'group should be redacted');
  assert.ok(result.includes('384B'), 'size should be preserved');
  assert.ok(result.includes('Feb 11 23:45'), 'date should be preserved');
  assert.ok(!result.includes('heathyeager'), 'username should not remain');
});

test('standalone username replaced', function () {
  const rules = buildRules();
  const { result } = applyRules('Author: heathyeager on host', rules);
  assert.strictEqual(result, 'Author: {{USER}} on host');
});

// --- Technical content preserved ---

test('timestamps, hashes, exit codes not redacted', function () {
  const input = '2026-02-11T13:44:05.029Z sha256=d5322d387a exitCode=0 policy=allowlist';
  const rules = buildRules();
  const { result } = applyRules(input, rules);
  assert.strictEqual(result, input, 'technical content should be unchanged');
});

test('placeholders are not themselves redactable patterns', function () {
  const input = '{{REPO_ROOT}}/foo {{HOME}}/.openclaw {{USER}} {{GROUP}}';
  const rules = buildRules();
  const { result } = applyRules(input, rules);
  assert.strictEqual(result, input, 'placeholders should pass through unchanged');
});

test('CLI redacts synthetic fixtures and writes output bundle', function () {
  const fixtureIn = path.resolve(__dirname, '..', 'fixtures', 'redaction', 'in');
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'clawd-redaction-'));
  const outputDir = path.join(tempRoot, 'out');

  const run = runCli(['--in', fixtureIn, '--out', outputDir, '--json']);
  assert.strictEqual(run.status, 0, 'CLI should exit 0');
  assert.ok(run.stdout.trim().startsWith('{'), 'CLI should emit JSON summary');

  const summary = JSON.parse(run.stdout);
  assert.ok(summary.files_scanned >= 3, 'should scan fixture files');
  assert.ok(summary.files_changed >= 3, 'should redact fixture files');

  const credentialsOut = fs.readFileSync(path.join(outputDir, 'credentials.txt'), 'utf8');
  const infoOut = fs.readFileSync(path.join(outputDir, 'system', 'info.md'), 'utf8');
  const metadataOut = fs.readFileSync(path.join(outputDir, 'metadata.json'), 'utf8');

  assert.ok(!credentialsOut.includes('sk-TEST1234567890ABCDE'), 'OpenAI-like key should be redacted');
  assert.ok(!credentialsOut.includes('ghp_FAKE123456789012345678901234567890'), 'GitHub-like key should be redacted');
  assert.ok(!credentialsOut.includes('/Users/demo'), 'absolute macOS path should be redacted');
  assert.ok(credentialsOut.includes('{{SECRET_TOKEN}}'), 'token placeholder should be present');
  assert.ok(credentialsOut.includes('{{EMAIL}}'), 'email placeholder should be present');
  assert.ok(credentialsOut.includes('{{HOST}}'), 'host placeholder should be present');

  assert.ok(!infoOut.includes('heathyeager'), 'username should be redacted in markdown fixture');
  assert.ok(infoOut.includes('{{USER}}'), 'username placeholder should be present');
  assert.ok(validateJson(metadataOut), 'redacted JSON output should remain valid JSON');
  assert.ok(!metadataOut.includes('sk-TESTABCDEFGHIJKLMN123456'), 'JSON token should be redacted');

  fs.rmSync(tempRoot, { recursive: true, force: true });
});

test('CLI dry-run emits summary and does not write output files', function () {
  const fixtureIn = path.resolve(__dirname, '..', 'fixtures', 'redaction', 'in');
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'clawd-redaction-dry-'));
  const outputDir = path.join(tempRoot, 'out');

  const run = runCli(['--in', fixtureIn, '--out', outputDir, '--json', '--dry-run']);
  assert.strictEqual(run.status, 0, 'dry-run should exit 0');
  const summary = JSON.parse(run.stdout);
  assert.strictEqual(summary.dry_run, true, 'summary should indicate dry-run mode');
  assert.strictEqual(fs.existsSync(outputDir), false, 'dry-run should not create output directory');

  fs.rmSync(tempRoot, { recursive: true, force: true });
});
