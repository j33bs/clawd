#!/usr/bin/env node
'use strict';

const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const FAIL_ON = [
  'snapshot_summary.log_signature_counts.auth_error',
  'snapshot_summary.log_signature_counts.quota_error',
  'snapshot_summary.log_signature_counts.fetch_error'
].join(',');

function test(name, fn) {
  try {
    fn();
    console.log('PASS ' + name);
  } catch (err) {
    console.error('FAIL ' + name + ': ' + err.message);
    process.exitCode = 1;
  }
}

function runCli(simulateName) {
  const scriptPath = path.resolve(__dirname, '..', 'scripts', 'system2_experiment.js');
  const fixtureDir = path.resolve(__dirname, '..', 'fixtures', 'system2_experiment', simulateName);
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), `clawd-exp-${simulateName}-`));

  const run = spawnSync(
    process.execPath,
    [
      scriptPath,
      '--out', outDir,
      '--fail-on', FAIL_ON,
      '--simulate', fixtureDir,
      '--no-prompt',
      '--label-a', 'baseline',
      '--label-b', 'candidate'
    ],
    { encoding: 'utf8' }
  );

  if (run.status !== 0) {
    throw new Error(`CLI failed (${run.status}): ${run.stderr}`);
  }

  const report = JSON.parse(run.stdout);
  const reportPath = path.join(outDir, 'report.json');
  const diffPath = path.join(outDir, 'diff.json');
  assert.ok(fs.existsSync(reportPath), 'report.json should be written');
  assert.ok(fs.existsSync(diffPath), 'diff.json should be written');

  const saved = JSON.parse(fs.readFileSync(reportPath, 'utf8'));
  assert.strictEqual(saved.decision, report.decision, 'stdout and report.json should match decision');

  return { outDir, report, saved };
}

test('no-change fixture yields INCONCLUSIVE', function () {
  const result = runCli('no_change');
  assert.strictEqual(result.report.diff_exit, 0);
  assert.strictEqual(result.report.regressions_count, 0);
  assert.strictEqual(result.report.decision, 'INCONCLUSIVE');
  fs.rmSync(result.outDir, { recursive: true, force: true });
});

test('improvement fixture yields KEEP', function () {
  const result = runCli('keep');
  assert.strictEqual(result.report.diff_exit, 2);
  assert.strictEqual(result.report.regressions_count, 0);
  assert.strictEqual(result.report.decision, 'KEEP');
  fs.rmSync(result.outDir, { recursive: true, force: true });
});

test('regression fixture yields REVERT', function () {
  const result = runCli('regression');
  assert.strictEqual(result.report.diff_exit, 2);
  assert.strictEqual(result.report.regressions_count, 1);
  assert.strictEqual(result.report.decision, 'REVERT');
  fs.rmSync(result.outDir, { recursive: true, force: true });
});

test('failing subprocess writes UNAVAILABLE report and exits 3', function () {
  const scriptPath = path.resolve(__dirname, '..', 'scripts', 'system2_experiment.js');
  const fixtureDir = path.resolve(__dirname, '..', 'fixtures', 'system2_experiment', 'diff_failure');
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), 'clawd-exp-diff-failure-'));

  const run = spawnSync(
    process.execPath,
    [
      scriptPath,
      '--out', outDir,
      '--fail-on', FAIL_ON,
      '--simulate', fixtureDir,
      '--no-prompt'
    ],
    { encoding: 'utf8' }
  );

  assert.strictEqual(run.status, 3, 'CLI should exit 3 on subprocess failure');

  const reportPath = path.join(outDir, 'report.json');
  assert.ok(fs.existsSync(reportPath), 'report.json should be written on failure');

  const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'));
  assert.strictEqual(report.status, 'ERROR');
  assert.strictEqual(report.decision, 'UNAVAILABLE');
  assert.ok(report.error, 'error object should be present');
  assert.strictEqual(report.error.stage, 'diff');
  assert.strictEqual(typeof report.error.stderr_tail, 'string');
  assert.ok(report.paths, 'paths object should be present');

  fs.rmSync(outDir, { recursive: true, force: true });
});
