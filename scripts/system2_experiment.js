#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const readline = require('node:readline/promises');
const { spawnSync } = require('node:child_process');

class StageError extends Error {
  constructor(message, options = {}) {
    super(message);
    this.name = 'StageError';
    this.stage = options.stage || 'unknown';
    this.exitCode = typeof options.exitCode === 'number' ? options.exitCode : null;
    this.stderrTail = options.stderrTail || '';
  }
}

function parseList(value) {
  if (!value) {
    return [];
  }
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseArgs(argv) {
  const args = {
    outDir: null,
    failOn: [],
    noPrompt: false,
    labelA: 'A',
    labelB: 'B',
    simulateDir: null
  };

  for (let i = 0; i < argv.length; i += 1) {
    const tok = argv[i];

    if (tok === '--out' && i + 1 < argv.length) {
      args.outDir = argv[++i];
      continue;
    }

    if (tok === '--fail-on' && i + 1 < argv.length) {
      args.failOn = parseList(argv[++i]);
      continue;
    }

    if (tok === '--no-prompt') {
      args.noPrompt = true;
      continue;
    }

    if (tok === '--label-a' && i + 1 < argv.length) {
      args.labelA = argv[++i];
      continue;
    }

    if (tok === '--label-b' && i + 1 < argv.length) {
      args.labelB = argv[++i];
      continue;
    }

    if (tok === '--simulate' && i + 1 < argv.length) {
      args.simulateDir = argv[++i];
      continue;
    }

    throw new Error(`Unknown or incomplete argument: ${tok}`);
  }

  if (!args.outDir) {
    throw new Error('--out <dir> is required');
  }

  if (args.failOn.length === 0) {
    throw new Error('--fail-on <comma,separated,dotpaths> is required');
  }

  return args;
}

function tailLines(value, maxLines = 20) {
  const text = typeof value === 'string' ? value.trim() : '';
  if (!text) {
    return '';
  }
  const lines = text.split(/\r?\n/);
  return lines.slice(-maxLines).join('\n');
}

function runNpmJson(args, acceptableCodes, stage) {
  const result = spawnSync('npm', ['run', '--silent', ...args], {
    encoding: 'utf8',
    maxBuffer: 20 * 1024 * 1024
  });

  const status = typeof result.status === 'number' ? result.status : 3;
  const allowed = new Set(acceptableCodes || [0]);
  if (!allowed.has(status)) {
    const stderr = (result.stderr || '').trim();
    throw new StageError(
      `command failed: npm run ${args.join(' ')} (exit ${status})${stderr ? `: ${stderr}` : ''}`,
      {
        stage: stage || 'unknown',
        exitCode: status,
        stderrTail: tailLines(stderr)
      }
    );
  }

  const stdout = (result.stdout || '').trim();
  if (!stdout) {
    throw new StageError(`command produced empty JSON output: npm run ${args.join(' ')}`, {
      stage: stage || 'unknown',
      exitCode: status,
      stderrTail: tailLines(result.stderr || '')
    });
  }

  try {
    return { status, json: JSON.parse(stdout) };
  } catch (error) {
    throw new StageError(`command produced invalid JSON output: npm run ${args.join(' ')} (${error.message})`, {
      stage: stage || 'unknown',
      exitCode: status,
      stderrTail: tailLines(result.stderr || '')
    });
  }
}

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function writeReport(reportPath, partial) {
  const report = partial && typeof partial === 'object'
    ? partial
    : {
        status: 'ERROR',
        decision: 'UNAVAILABLE'
      };
  ensureDir(path.dirname(reportPath));
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2) + '\n', 'utf8');
  return report;
}

function copySnapshotSummary(simulateDir, label, targetRunDir) {
  const source = path.resolve(simulateDir, `run${label}`, 'snapshot_summary.json');
  if (!fs.existsSync(source)) {
    throw new Error(`simulate fixture missing: ${source}`);
  }
  ensureDir(targetRunDir);
  fs.copyFileSync(source, path.join(targetRunDir, 'snapshot_summary.json'));
}

async function promptForChange(message) {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });
  try {
    await rl.question(message);
  } finally {
    rl.close();
  }
}

function normalizePathForReport(absPath) {
  return path.relative(process.cwd(), absPath) || '.';
}

function findSnapshotSummary(runDir) {
  const candidates = [
    path.join(runDir, 'snapshot_summary.json'),
    path.join(runDir, 'raw', 'snapshot_summary.json'),
    path.join(runDir, 'snapshot-summary.json')
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return null;
}

function ensureJsonFileExists(filePath, stage, label) {
  if (!fs.existsSync(filePath)) {
    throw new StageError(`${label} missing: ${filePath}`, { stage });
  }
}

function safeReadJson(filePath, stage, label) {
  ensureJsonFileExists(filePath, stage, label);
  let raw;
  try {
    raw = fs.readFileSync(filePath, 'utf8');
  } catch (error) {
    throw new StageError(`${label} unreadable: ${filePath} (${error.message})`, { stage });
  }

  try {
    return JSON.parse(raw);
  } catch (error) {
    throw new StageError(`${label} invalid JSON: ${filePath} (${error.message})`, { stage });
  }
}

function decide(diffJson, diffExit) {
  const changedCount = Array.isArray(diffJson.changed) ? diffJson.changed.length : 0;
  const addedCount = Array.isArray(diffJson.added) ? diffJson.added.length : 0;
  const removedCount = Array.isArray(diffJson.removed) ? diffJson.removed.length : 0;
  const regressionsCount = Array.isArray(diffJson.regressions) ? diffJson.regressions.length : 0;

  const rationale = [];
  let decision = 'INCONCLUSIVE';

  if (diffExit === 0) {
    decision = 'INCONCLUSIVE';
    rationale.push('No measurable delta detected (or only ignored noise).');
  } else if (regressionsCount > 0) {
    decision = 'REVERT';
    rationale.push('Regression detected on fail-on path(s).');
  } else if (changedCount + addedCount + removedCount > 0) {
    decision = 'KEEP';
    rationale.push('Changes detected with no regressions on fail-on path(s).');
  } else {
    decision = 'INCONCLUSIVE';
    rationale.push('Diff exit indicated change, but no structured deltas were found.');
  }

  return { decision, rationale, regressionsCount };
}

async function runExperiment(options) {
  const outDir = path.resolve(options.outDir);
  const runADir = path.join(outDir, 'runA');
  const runBDir = path.join(outDir, 'runB');
  const diffPath = path.join(outDir, 'diff.json');
  const reportPath = path.join(outDir, 'report.json');
  const reportPaths = {
    out: normalizePathForReport(outDir),
    runA: normalizePathForReport(runADir),
    runB: normalizePathForReport(runBDir),
    diffJson: normalizePathForReport(diffPath),
    reportJson: normalizePathForReport(reportPath)
  };

  fs.rmSync(outDir, { recursive: true, force: true });
  ensureDir(runADir);
  ensureDir(runBDir);

  let runASummaryPath;
  let runBSummaryPath;
  let currentStage = 'evidence_A';

  try {
    if (options.simulateDir) {
      copySnapshotSummary(options.simulateDir, 'A', runADir);
      runASummaryPath = findSnapshotSummary(runADir);
      if (!runASummaryPath) {
        throw new StageError(`snapshot summary path missing after ${currentStage}`, { stage: currentStage });
      }

      currentStage = 'evidence_B';
      copySnapshotSummary(options.simulateDir, 'B', runBDir);
      runBSummaryPath = findSnapshotSummary(runBDir);
      if (!runBSummaryPath) {
        throw new StageError(`snapshot summary path missing after ${currentStage}`, { stage: currentStage });
      }
    } else {
      runNpmJson(['system2:evidence', '--', '--out', runADir], [0], currentStage);
      runASummaryPath = findSnapshotSummary(runADir);
      if (!runASummaryPath) {
        throw new StageError(`snapshot summary path missing after ${currentStage}`, { stage: currentStage });
      }

      if (!options.noPrompt) {
        if (!process.stdin.isTTY) {
          throw new StageError('interactive prompt requested in non-interactive session; use --no-prompt', {
            stage: currentStage
          });
        }
        await promptForChange('Make your single operator change now, then press Enter to continue... ');
      }

      currentStage = 'evidence_B';
      runNpmJson(['system2:evidence', '--', '--out', runBDir], [0], currentStage);
      runBSummaryPath = findSnapshotSummary(runBDir);
      if (!runBSummaryPath) {
        throw new StageError(`snapshot summary path missing after ${currentStage}`, { stage: currentStage });
      }
    }

    const failOnCsv = options.failOn.join(',');
    currentStage = 'diff';
    const diffRun = runNpmJson(
      ['system2:diff', '--', '--a', runASummaryPath, '--b', runBSummaryPath, '--json', '--fail-on', failOnCsv],
      [0, 2],
      currentStage
    );

    fs.writeFileSync(diffPath, JSON.stringify(diffRun.json, null, 2) + '\n', 'utf8');
    const diffJson = safeReadJson(diffPath, currentStage, 'diff.json');

    currentStage = 'report_write';
    const decision = decide(diffJson, diffRun.status);
    const report = {
      out_dir: normalizePathForReport(outDir),
      runA: {
        label: options.labelA,
        summary_path: normalizePathForReport(runASummaryPath)
      },
      runB: {
        label: options.labelB,
        summary_path: normalizePathForReport(runBSummaryPath)
      },
      diff_exit: diffRun.status,
      regressions_count: decision.regressionsCount,
      decision: decision.decision,
      rationale: decision.rationale,
      fail_on: options.failOn
    };

    writeReport(reportPath, report);
    return report;
  } catch (error) {
    const stageError = error instanceof StageError
      ? error
      : new StageError(error.message || String(error), { stage: currentStage });

    writeReport(reportPath, {
      status: 'ERROR',
      decision: 'UNAVAILABLE',
      error: {
        stage: stageError.stage || currentStage,
        exitCode: stageError.exitCode,
        stderr_tail: stageError.stderrTail || ''
      },
      paths: reportPaths
    });

    throw stageError;
  }
}

async function main() {
  let args;

  try {
    args = parseArgs(process.argv.slice(2));
    const report = await runExperiment(args);
    console.log(JSON.stringify(report, null, 2));
  } catch (error) {
    console.error(`system2:experiment failed: ${error.message}`);
    process.exit(3);
  }
}

if (require.main === module) {
  main();
}

module.exports = {
  decide,
  parseArgs,
  runExperiment
};
