'use strict';

const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');

const DEFAULT_COMMIT = '9f35bc1ab7d802e60923c95679febc0325555007';
const DEFAULT_OUTPUT = 'workspace/docs/audits/SALVAGE-REPORT-system2-unified-2026-02-12.md';

function runGit(args) {
  return cp.execFileSync('git', args, { encoding: 'utf8' });
}

function parseArgs(argv) {
  const out = { commit: DEFAULT_COMMIT, output: DEFAULT_OUTPUT };
  for (let i = 2; i < argv.length; i += 1) {
    if (argv[i] === '--commit' && argv[i + 1]) out.commit = argv[++i];
    else if (argv[i] === '--output' && argv[i + 1]) out.output = argv[++i];
  }
  return out;
}

function parseSpecs(source) {
  const specs = [];
  const patterns = [
    /require\(\s*['"](\.{1,2}\/[^'"]+)['"]\s*\)/g,
    /import\s+[^'"]*?\s+from\s+['"](\.{1,2}\/[^'"]+)['"]/g,
    /import\(\s*['"](\.{1,2}\/[^'"]+)['"]\s*\)/g
  ];
  for (const re of patterns) {
    let m;
    while ((m = re.exec(source)) !== null) {
      specs.push(m[1]);
    }
  }
  return specs;
}

function resolveCandidates(filePath, spec) {
  const baseDir = path.posix.dirname(filePath);
  const resolvedBase = path.posix.normalize(path.posix.join(baseDir, spec));
  return [
    resolvedBase,
    `${resolvedBase}.js`,
    `${resolvedBase}.cjs`,
    `${resolvedBase}.mjs`,
    `${resolvedBase}.ts`,
    `${resolvedBase}.json`,
    path.posix.join(resolvedBase, 'index.js'),
    path.posix.join(resolvedBase, 'index.ts'),
    path.posix.join(resolvedBase, 'index.json')
  ];
}

function mdEscape(value) {
  return String(value).replace(/\|/g, '\\|');
}

function main() {
  const args = parseArgs(process.argv);
  const commit = args.commit;
  const outputPath = args.output;

  runGit(['cat-file', '-e', `${commit}^{commit}`]);
  const treeFiles = runGit(['ls-tree', '-r', '--name-only', commit])
    .split('\n')
    .map((v) => v.trim())
    .filter(Boolean);
  const fileSet = new Set(treeFiles);
  const codeFiles = treeFiles.filter((f) => /\.(cjs|mjs|js|ts)$/.test(f));

  const missing = [];
  for (const filePath of codeFiles) {
    const source = runGit(['show', `${commit}:${filePath}`]);
    const specs = parseSpecs(source);
    for (const spec of specs) {
      const candidates = resolveCandidates(filePath, spec);
      const found = candidates.some((c) => fileSet.has(c));
      if (!found) {
        missing.push({ filePath, spec });
      }
    }
  }

  const counts = new Map();
  for (const item of missing) {
    counts.set(item.filePath, (counts.get(item.filePath) || 0) + 1);
  }
  const topFiles = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 20);

  const now = new Date().toISOString();
  const lines = [];
  lines.push('# SALVAGE REPORT: system2 unified integration');
  lines.push('');
  lines.push(`- Generated at: ${now}`);
  lines.push(`- Analyzed commit: \`${commit}\``);
  lines.push(`- File inventory size: ${treeFiles.length}`);
  lines.push(`- Code files scanned: ${codeFiles.length}`);
  lines.push(`- Findings: ${missing.length} MISSING_RELATIVE_REQUIRE entries`);
  lines.push('');
  lines.push('## Counts by File (Top Offenders)');
  lines.push('');
  lines.push('| File | Missing Relative Requires |');
  lines.push('| --- | ---: |');
  for (const [filePath, count] of topFiles) {
    lines.push(`| ${mdEscape(filePath)} | ${count} |`);
  }
  lines.push('');
  lines.push('## Findings');
  lines.push('');
  lines.push('| Type | File | Specifier |');
  lines.push('| --- | --- | --- |');
  for (const item of missing) {
    lines.push(
      `| MISSING_RELATIVE_REQUIRE | ${mdEscape(item.filePath)} | ${mdEscape(item.spec)} |`
    );
  }
  lines.push('');
  lines.push('## Suggested Minimal Remediation Strategies (Not Applied)');
  lines.push('');
  lines.push('- Restore missing sibling modules that existing relative paths already reference.');
  lines.push('- Prefer targeted path corrections only where specifier typos are proven.');
  lines.push('- Add narrow compatibility entrypoints (for example index.js wrappers) only when needed.');
  lines.push('- Avoid broad refactors; re-run deterministic tests after each small patch set.');
  lines.push('');

  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, `${lines.join('\n')}\n`, 'utf8');
  console.log(`Wrote ${outputPath} with ${missing.length} findings.`);
}

main();
