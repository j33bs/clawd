#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const PATTERNS = Object.freeze([
  {
    id: 'all_models_failed',
    title: 'All Models Failed',
    regex: /\ball models failed\b/i,
    recommendation: 'Audit routing order and provider readiness before retry loops.'
  },
  {
    id: 'cooldown_loop',
    title: 'Cooldown Loop',
    regex: /\bcooldown\b.*\b(loop|retry|again)\b/i,
    recommendation: 'Add bounded backoff with a fail-fast threshold to stop repeated cooldown retries.'
  },
  {
    id: 'local_fallback_auth_error',
    title: 'Local Fallback Auth Error',
    regex: /\b(local fallback|fallback local)\b.*\b(auth|unauthorized|login required)\b/i,
    recommendation: 'Validate local auth prerequisites before attempting fallback.'
  }
]);

function resolveRepoRoot(startDir) {
  let current = path.resolve(startDir || process.cwd());
  for (let i = 0; i < 8; i += 1) {
    if (fs.existsSync(path.join(current, '.git'))) return current;
    const parent = path.dirname(current);
    if (parent === current) break;
    current = parent;
  }
  throw new Error('repo root not found');
}

function utcDate(date = new Date()) {
  return date.toISOString().slice(0, 10);
}

function listMemoryFiles(memoryDir) {
  if (!fs.existsSync(memoryDir)) return [];
  return fs.readdirSync(memoryDir)
    .filter((name) => name.endsWith('.md'))
    .sort()
    .map((name) => path.join(memoryDir, name));
}

function analyzeSessions({ memoryDir, patterns = PATTERNS }) {
  const files = listMemoryFiles(memoryDir);
  const findings = new Map();
  for (const pattern of patterns) {
    findings.set(pattern.id, {
      id: pattern.id,
      title: pattern.title,
      recommendation: pattern.recommendation,
      total: 0,
      files: []
    });
  }

  for (const filePath of files) {
    const rel = path.basename(filePath);
    const lines = fs.readFileSync(filePath, 'utf8').split(/\r?\n/);
    for (const pattern of patterns) {
      const matches = [];
      for (let i = 0; i < lines.length; i += 1) {
        if (pattern.regex.test(lines[i])) {
          matches.push(i + 1);
        }
      }
      if (matches.length > 0) {
        const row = findings.get(pattern.id);
        row.total += matches.length;
        row.files.push({ file: rel, lines: matches });
      }
    }
  }

  return {
    scannedFiles: files.map((f) => path.basename(f)),
    findings: Array.from(findings.values())
  };
}

function renderReport({ dateKey, scannedFiles, findings }) {
  const lines = [
    '# Session Pattern Report',
    '',
    `- date_utc: ${dateKey}`,
    `- memory_files_scanned: ${scannedFiles.length}`,
    ''
  ];

  if (scannedFiles.length > 0) {
    lines.push('## Files');
    for (const file of scannedFiles) {
      lines.push(`- ${file}`);
    }
    lines.push('');
  }

  lines.push('## Findings');
  let hasFinding = false;
  for (const finding of findings) {
    if (finding.total <= 0) continue;
    hasFinding = true;
    lines.push(`### ${finding.title}`);
    lines.push(`- id: ${finding.id}`);
    lines.push(`- total_hits: ${finding.total}`);
    lines.push(`- recommendation: ${finding.recommendation}`);
    for (const fileEntry of finding.files) {
      lines.push(`- file: ${fileEntry.file} lines=${fileEntry.lines.join(',')}`);
    }
    lines.push('');
  }

  if (!hasFinding) {
    lines.push('- none');
    lines.push('');
  }

  return `${lines.join('\n')}\n`;
}

function writePatternReport({ repoRoot, dateKey, result, outPath }) {
  const targetPath = outPath
    ? (path.isAbsolute(outPath) ? outPath : path.join(repoRoot, outPath))
    : path.join(repoRoot, 'workspace', 'reports', `session-patterns-${dateKey}.md`);
  fs.mkdirSync(path.dirname(targetPath), { recursive: true });
  const report = renderReport({
    dateKey,
    scannedFiles: result.scannedFiles,
    findings: result.findings
  });
  fs.writeFileSync(targetPath, report, 'utf8');
  return targetPath;
}

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === '--date' && argv[i + 1]) {
      out.date = argv[i + 1];
      i += 1;
    } else if (a === '--memory-dir' && argv[i + 1]) {
      out.memoryDir = argv[i + 1];
      i += 1;
    } else if (a === '--output' && argv[i + 1]) {
      out.output = argv[i + 1];
      i += 1;
    }
  }
  return out;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const repoRoot = resolveRepoRoot(process.cwd());
  const dateKey = args.date || utcDate();
  const memoryDir = args.memoryDir
    ? path.resolve(args.memoryDir)
    : path.join(repoRoot, 'workspace', 'memory');
  const result = analyzeSessions({ memoryDir });
  const outPath = writePatternReport({ repoRoot, dateKey, result, outPath: args.output });
  process.stdout.write(`${path.relative(repoRoot, outPath)}\n`);
}

if (require.main === module) {
  try {
    main();
  } catch (error) {
    process.stderr.write(`analyze_session_patterns failed: ${error.message}\n`);
    process.exit(1);
  }
}

module.exports = {
  PATTERNS,
  analyzeSessions,
  renderReport,
  writePatternReport
};
