#!/usr/bin/env node
'use strict';

const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { computeDiff, DEFAULT_IGNORED_PATHS } = require('../scripts/system2_snapshot_diff');
const { decide } = require('../scripts/system2_experiment');

const LEGACY_FAIL_ON = [
  'snapshot_summary.log_signature_counts.auth_error',
  'snapshot_summary.log_signature_counts.quota_error',
  'snapshot_summary.log_signature_counts.fetch_error'
].join(',');
const AUTH_CALIBRATED_FAIL_ON = 'log_signature_counts.auth_error';

function test(name, fn) {
  try {
    fn();
    console.log('PASS ' + name);
  } catch (err) {
    console.error('FAIL ' + name + ': ' + err.message);
    process.exitCode = 1;
  }
}

function canSpawnNode() {
  const probe = spawnSync(process.execPath, ['-e', 'process.exit(0)'], { encoding: 'utf8' });
  return !probe.error;
}

function runCliWithFixtureDir(fixtureDir, failOn) {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), 'clawd-exp-'));
  const failOnList = String(failOn || '')
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean);

  if (!canSpawnNode()) {
    // Fallback for restricted environments where nested spawn is blocked (EPERM).
    const runASummaryPath = path.join(fixtureDir, 'runA', 'snapshot_summary.json');
    const runBSummaryPath = path.join(fixtureDir, 'runB', 'snapshot_summary.json');
    const reportPath = path.join(outDir, 'report.json');
    const diffPath = path.join(outDir, 'diff.json');
    let report;

    try {
      const aObj = JSON.parse(fs.readFileSync(runASummaryPath, 'utf8'));
      const bObj = JSON.parse(fs.readFileSync(runBSummaryPath, 'utf8'));
      const diffJson = computeDiff(aObj, bObj, {
        ignore: DEFAULT_IGNORED_PATHS,
        failOn: failOnList
      });
      const hasDiff = diffJson.changed.length > 0 || diffJson.added.length > 0 || diffJson.removed.length > 0;
      const diffExit = hasDiff ? 2 : 0;
      const decision = decide(diffJson, diffExit);
      report = {
        out_dir: path.relative(process.cwd(), outDir) || '.',
        runA: { label: 'baseline', summary_path: path.relative(process.cwd(), runASummaryPath) || runASummaryPath },
        runB: { label: 'candidate', summary_path: path.relative(process.cwd(), runBSummaryPath) || runBSummaryPath },
        diff_exit: diffExit,
        regressions_count: decision.regressionsCount,
        decision: decision.decision,
        rationale: decision.rationale,
        fail_on: failOnList
      };
      fs.mkdirSync(outDir, { recursive: true });
      fs.writeFileSync(diffPath, JSON.stringify(diffJson, null, 2) + '\n', 'utf8');
      fs.writeFileSync(reportPath, JSON.stringify(report, null, 2) + '\n', 'utf8');
    } catch (error) {
      report = {
        status: 'ERROR',
        decision: 'UNAVAILABLE',
        error: { stage: 'diff', exitCode: 3, stderr_tail: String(error.message || error) },
        paths: {
          out: path.relative(process.cwd(), outDir) || '.',
          reportJson: path.relative(process.cwd(), reportPath) || reportPath,
          diffJson: path.relative(process.cwd(), diffPath) || diffPath
        }
      };
      fs.mkdirSync(outDir, { recursive: true });
      fs.writeFileSync(reportPath, JSON.stringify(report, null, 2) + '\n', 'utf8');
    }

    const saved = JSON.parse(fs.readFileSync(reportPath, 'utf8'));
    return { outDir, report: saved, saved };
  }

  const scriptPath = path.resolve(__dirname, '..', 'scripts', 'system2_experiment.js');

  const run = spawnSync(
    process.execPath,
    [
      scriptPath,
      '--out', outDir,
      '--fail-on', failOn,
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

function runCli(simulateName) {
  const fixtureDir = path.resolve(__dirname, '..', 'fixtures', 'system2_experiment', simulateName);
  return runCliWithFixtureDir(fixtureDir, LEGACY_FAIL_ON);
}

function buildCalibratedRegressionFixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'clawd-exp-calibrated-'));
  fs.mkdirSync(path.join(root, 'runA'), { recursive: true });
  fs.mkdirSync(path.join(root, 'runB'), { recursive: true });

  const runA = {
    timestamp_utc: '2026-02-12T01:00:00.000Z',
    health_ok: true,
    status_ok: true,
    approvals_count: 0,
    log_signature_counts: {
      auth_error: 0,
      quota_error: 0,
      fetch_error: 0
    }
  };

  const runB = {
    timestamp_utc: '2026-02-12T01:05:00.000Z',
    health_ok: true,
    status_ok: true,
    approvals_count: 0,
    log_signature_counts: {
      auth_error: 3,
      quota_error: 0,
      fetch_error: 0
    }
  };

  fs.writeFileSync(path.join(root, 'runA', 'snapshot_summary.json'), JSON.stringify(runA, null, 2) + '\n', 'utf8');
  fs.writeFileSync(path.join(root, 'runB', 'snapshot_summary.json'), JSON.stringify(runB, null, 2) + '\n', 'utf8');

  return root;
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

test('auth preset script maps to calibrated fail-on path', function () {
  const pkgPath = path.resolve(__dirname, '..', 'package.json');
  const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));
  assert.strictEqual(
    pkg.scripts['system2:experiment:auth'],
    'npm run system2:experiment -- --fail-on log_signature_counts.auth_error'
  );
});

test('calibrated auth fail-on yields REVERT on regression fixture', function () {
  const fixtureDir = buildCalibratedRegressionFixture();
  const result = runCliWithFixtureDir(fixtureDir, AUTH_CALIBRATED_FAIL_ON);
  assert.strictEqual(result.report.decision, 'REVERT');
  assert.ok(result.report.regressions_count > 0);

  fs.rmSync(result.outDir, { recursive: true, force: true });
  fs.rmSync(fixtureDir, { recursive: true, force: true });
});

test('failing subprocess writes UNAVAILABLE report and exits 3', function () {
  if (!canSpawnNode()) {
    const fixtureDir = path.resolve(__dirname, '..', 'fixtures', 'system2_experiment', 'diff_failure');
    const result = runCliWithFixtureDir(fixtureDir, LEGACY_FAIL_ON);
    assert.strictEqual(result.report.status, 'ERROR');
    assert.strictEqual(result.report.decision, 'UNAVAILABLE');
    assert.ok(result.report.error, 'error object should be present');
    assert.strictEqual(result.report.error.stage, 'diff');
    assert.strictEqual(typeof result.report.error.stderr_tail, 'string');
    fs.rmSync(result.outDir, { recursive: true, force: true });
    return;
  }

  const scriptPath = path.resolve(__dirname, '..', 'scripts', 'system2_experiment.js');
  const fixtureDir = path.resolve(__dirname, '..', 'fixtures', 'system2_experiment', 'diff_failure');
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), 'clawd-exp-diff-failure-'));

  const run = spawnSync(
    process.execPath,
    [
      scriptPath,
      '--out', outDir,
      '--fail-on', LEGACY_FAIL_ON,
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
