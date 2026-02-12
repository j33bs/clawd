#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const readline = require('node:readline/promises');
const { spawnSync } = require('node:child_process');

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

function runNpmJson(args, acceptableCodes) {
  const result = spawnSync('npm', ['run', '--silent', ...args], {
    encoding: 'utf8',
    maxBuffer: 20 * 1024 * 1024
  });

  const status = typeof result.status === 'number' ? result.status : 3;
  const allowed = new Set(acceptableCodes || [0]);
  if (!allowed.has(status)) {
    const stderr = (result.stderr || '').trim();
    throw new Error(`command failed: npm run ${args.join(' ')} (exit ${status})${stderr ? `: ${stderr}` : ''}`);
  }

  const stdout = (result.stdout || '').trim();
  if (!stdout) {
    throw new Error(`command produced empty JSON output: npm run ${args.join(' ')}`);
  }

  try {
    return { status, json: JSON.parse(stdout) };
  } catch (error) {
    throw new Error(`command produced invalid JSON output: npm run ${args.join(' ')} (${error.message})`);
  }
}

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
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

  fs.rmSync(outDir, { recursive: true, force: true });
  ensureDir(runADir);
  ensureDir(runBDir);

  let runASummaryPath;
  let runBSummaryPath;

  if (options.simulateDir) {
    copySnapshotSummary(options.simulateDir, 'A', runADir);
    copySnapshotSummary(options.simulateDir, 'B', runBDir);
    runASummaryPath = path.join(runADir, 'snapshot_summary.json');
    runBSummaryPath = path.join(runBDir, 'snapshot_summary.json');
  } else {
    runNpmJson(['system2:evidence', '--', '--out', runADir], [0]);
    runASummaryPath = path.join(runADir, 'raw', 'snapshot_summary.json');

    if (!options.noPrompt) {
      if (!process.stdin.isTTY) {
        throw new Error('interactive prompt requested in non-interactive session; use --no-prompt');
      }
      await promptForChange('Make your single operator change now, then press Enter to continue... ');
    }

    runNpmJson(['system2:evidence', '--', '--out', runBDir], [0]);
    runBSummaryPath = path.join(runBDir, 'raw', 'snapshot_summary.json');
  }

  if (!fs.existsSync(runASummaryPath) || !fs.existsSync(runBSummaryPath)) {
    throw new Error('snapshot summary path missing after evidence capture');
  }

  const failOnCsv = options.failOn.join(',');
  const diffRun = runNpmJson(
    ['system2:diff', '--', '--a', runASummaryPath, '--b', runBSummaryPath, '--json', '--fail-on', failOnCsv],
    [0, 2]
  );

  fs.writeFileSync(diffPath, JSON.stringify(diffRun.json, null, 2) + '\n', 'utf8');

  const decision = decide(diffRun.json, diffRun.status);

  const report = {
    out_dir: path.relative(process.cwd(), outDir) || '.',
    runA: {
      label: options.labelA,
      summary_path: path.relative(process.cwd(), runASummaryPath) || runASummaryPath
    },
    runB: {
      label: options.labelB,
      summary_path: path.relative(process.cwd(), runBSummaryPath) || runBSummaryPath
    },
    diff_exit: diffRun.status,
    regressions_count: decision.regressionsCount,
    decision: decision.decision,
    rationale: decision.rationale,
    fail_on: options.failOn
  };

  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2) + '\n', 'utf8');

  return report;
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
