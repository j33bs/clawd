'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

function run(cmd, args, options = {}) {
  return spawnSync(cmd, args, {
    stdio: options.inherit ? 'inherit' : 'pipe',
    encoding: 'utf8'
  });
}

function choosePython() {
  const candidates =
    process.platform === 'win32'
      ? [
          { cmd: 'py', args: ['-3'] },
          { cmd: 'python', args: [] }
        ]
      : [
          { cmd: 'python3', args: [] },
          { cmd: 'python', args: [] }
        ];

  for (const candidate of candidates) {
    const probe = run(candidate.cmd, [...candidate.args, '--version']);
    if (probe.status === 0) {
      return candidate;
    }
  }

  return null;
}

function collectNodeTests(rootDir) {
  const tests = [];
  if (!fs.existsSync(rootDir)) {
    return tests;
  }

  for (const entry of fs.readdirSync(rootDir, { withFileTypes: true })) {
    const fullPath = path.join(rootDir, entry.name);
    if (entry.isDirectory()) {
      tests.push(...collectNodeTests(fullPath));
      continue;
    }
    if (entry.isFile() && entry.name.endsWith('.test.js')) {
      tests.push(fullPath);
    }
  }

  return tests;
}

const pyTestsDir = path.resolve('tests_unittest');
const nodeTestsDir = path.resolve('tests');
const nodeTests = collectNodeTests(nodeTestsDir).sort();

let failures = 0;
let ran = 0;

if (fs.existsSync(pyTestsDir)) {
  const py = choosePython();
  if (!py) {
    console.error('No Python interpreter found for tests_unittest.');
    process.exit(1);
  }
  console.log(`RUN ${py.cmd} ${py.args.join(' ')} -m unittest discover -s tests_unittest -p test_*.py`);
  const pyRun = run(
    py.cmd,
    [...py.args, '-m', 'unittest', 'discover', '-s', 'tests_unittest', '-p', 'test_*.py'],
    { inherit: true }
  );
  ran += 1;
  if (pyRun.status !== 0) {
    failures += 1;
  }
}

for (const testFile of nodeTests) {
  const rel = path.relative(process.cwd(), testFile);
  console.log(`RUN node ${rel}`);
  const nodeRun = run(process.execPath, [testFile], { inherit: true });
  ran += 1;
  if (nodeRun.status !== 0) {
    failures += 1;
  }
}

if (ran === 0) {
  console.error('No tests discovered.');
  process.exit(1);
}

if (failures > 0) {
  console.error(`FAILURES: ${failures}/${ran}`);
  process.exit(1);
}

console.log(`OK ${ran} test group(s)`);
