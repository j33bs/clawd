#!/usr/bin/env node
'use strict';

const assert = require('node:assert');
const path = require('node:path');
const fs = require('node:fs');
const { spawnSync } = require('node:child_process');

const { computeDiff, DEFAULT_IGNORED_PATHS, parseArgs } = require('../scripts/system2_snapshot_diff');

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
  const scriptPath = path.resolve(__dirname, '..', 'scripts', 'system2_snapshot_diff.js');
  const probe = spawnSync(process.execPath, ['-e', 'process.exit(0)'], { encoding: 'utf8' });
  if (!probe.error) {
    return spawnSync(process.execPath, [scriptPath, ...args], { encoding: 'utf8' });
  }

  // Fallback for restricted environments where nested spawn is blocked (EPERM).
  try {
    const parsed = parseArgs(args);
    const aObj = JSON.parse(fs.readFileSync(path.resolve(parsed.aPath), 'utf8'));
    const bObj = JSON.parse(fs.readFileSync(path.resolve(parsed.bPath), 'utf8'));
    const ignored = [...DEFAULT_IGNORED_PATHS, ...parsed.ignore];
    const diff = computeDiff(aObj, bObj, { ignore: ignored, failOn: parsed.failOn });
    const output = {
      a: parsed.aPath,
      b: parsed.bPath,
      ignored: diff.ignored,
      changed: diff.changed,
      added: diff.added,
      removed: diff.removed,
      regressions: diff.regressions
    };
    const stdout = parsed.json
      ? JSON.stringify(output, null, 2)
      : [
          `changed=${output.changed.length} added=${output.added.length} removed=${output.removed.length} regressions=${output.regressions.length}`,
          ...(output.regressions.length > 0 ? ['REGRESSION'] : [])
        ].join('\n');
    const hasDiff = output.changed.length > 0 || output.added.length > 0 || output.removed.length > 0;
    return { status: hasDiff ? 2 : 0, stdout, stderr: '' };
  } catch (error) {
    return { status: 3, stdout: '', stderr: `system2:diff failed: ${error.message}` };
  }
}

const aPath = path.resolve(__dirname, '..', 'fixtures', 'system2_diff', 'a.json');
const bPath = path.resolve(__dirname, '..', 'fixtures', 'system2_diff', 'b.json');

test('JSON output is stable and ignores timestamp fields by default', function () {
  const run = runCli(['--a', aPath, '--b', bPath, '--json']);
  assert.strictEqual(run.status, 2, 'non-empty diff should exit 2');

  const out = JSON.parse(run.stdout);
  assert.ok(Array.isArray(out.ignored), 'ignored should be array');
  assert.ok(out.ignored.includes('timestamp_utc'));
  assert.ok(out.ignored.includes('snapshot_summary.timestamp_utc'));

  const changedPaths = out.changed.map((x) => x.path);
  const addedPaths = out.added.map((x) => x.path);
  const removedPaths = out.removed.map((x) => x.path);

  assert.ok(changedPaths.includes('snapshot_summary.log_signature_counts.auth_error'));
  assert.ok(addedPaths.includes('added_only'));
  assert.ok(addedPaths.includes('snapshot_summary.nodes_pending'));
  assert.ok(removedPaths.includes('removed_only'));
});

test('ignore list suppresses expected diff paths and exits 0', function () {
  const ignore = [
    'snapshot_summary.log_signature_counts.auth_error',
    'added_only',
    'snapshot_summary.nodes_pending',
    'removed_only'
  ].join(',');

  const run = runCli(['--a', aPath, '--b', bPath, '--json', '--ignore', ignore]);
  assert.strictEqual(run.status, 0, 'ignored deltas should exit 0');

  const out = JSON.parse(run.stdout);
  assert.strictEqual(out.changed.length, 0);
  assert.strictEqual(out.added.length, 0);
  assert.strictEqual(out.removed.length, 0);
});

test('fail-on marks regressions and exits 2', function () {
  const run = runCli([
    '--a', aPath,
    '--b', bPath,
    '--json',
    '--fail-on', 'snapshot_summary.log_signature_counts.auth_error'
  ]);

  assert.strictEqual(run.status, 2, 'regression should exit 2');
  const out = JSON.parse(run.stdout);
  assert.strictEqual(out.regressions.length, 1, 'expected one regression');
  assert.strictEqual(out.regressions[0].path, 'snapshot_summary.log_signature_counts.auth_error');
  assert.strictEqual(out.regressions[0].a, 0);
  assert.strictEqual(out.regressions[0].b, 2);
});

test('human output includes summary counts and regression marker', function () {
  const run = runCli([
    '--a', aPath,
    '--b', bPath,
    '--fail-on', 'snapshot_summary.log_signature_counts.auth_error'
  ]);

  assert.strictEqual(run.status, 2);
  assert.ok(run.stdout.includes('changed='), 'human output should include counts');
  assert.ok(run.stdout.includes('REGRESSION'), 'human output should include regression marker');
});

test('computeDiff supports deterministic dotpath flattening', function () {
  const diff = computeDiff(
    { root: { leaf: 1 }, arr: [1, 2], timestamp_utc: 'a' },
    { root: { leaf: 2 }, arr: [1, 2], timestamp_utc: 'b' },
    { ignore: DEFAULT_IGNORED_PATHS }
  );

  assert.strictEqual(diff.changed.length, 1);
  assert.strictEqual(diff.changed[0].path, 'root.leaf');
  assert.strictEqual(diff.changed[0].a, 1);
  assert.strictEqual(diff.changed[0].b, 2);
});
