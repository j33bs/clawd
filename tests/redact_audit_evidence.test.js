#!/usr/bin/env node
'use strict';

const assert = require('assert');
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
