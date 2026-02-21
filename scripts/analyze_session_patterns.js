#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { Worker, isMainThread, parentPort, workerData } = require('node:worker_threads');

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

function initFindings(patterns) {
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
  return findings;
}

function scanFileStreamSync(filePath, patterns, options = {}) {
  const stopWhenAllMatched = Boolean(options.stopWhenAllMatched);
  const matchesByPattern = Object.create(null);
  for (const pattern of patterns) {
    matchesByPattern[pattern.id] = [];
  }
  const seenAny = new Set();

  const fd = fs.openSync(filePath, 'r');
  const chunk = Buffer.allocUnsafe(64 * 1024);
  let carry = '';
  let lineNo = 0;

  try {
    while (true) {
      const bytes = fs.readSync(fd, chunk, 0, chunk.length, null);
      if (bytes <= 0) break;
      const text = carry + chunk.toString('utf8', 0, bytes);
      const lines = text.split(/\r?\n/);
      carry = lines.pop() || '';
      for (const line of lines) {
        lineNo += 1;
        for (const pattern of patterns) {
          if (pattern.regex.test(line)) {
            matchesByPattern[pattern.id].push(lineNo);
            seenAny.add(pattern.id);
          }
        }
        if (stopWhenAllMatched && seenAny.size === patterns.length) {
          return matchesByPattern;
        }
      }
    }

    if (carry.length > 0) {
      lineNo += 1;
      for (const pattern of patterns) {
        if (pattern.regex.test(carry)) {
          matchesByPattern[pattern.id].push(lineNo);
        }
      }
    }
  } finally {
    fs.closeSync(fd);
  }
  return matchesByPattern;
}

function aggregateFindings(files, patterns, fileMatchesMap) {
  const findings = initFindings(patterns);
  for (const filePath of files) {
    const rel = path.basename(filePath);
    const matchesByPattern = fileMatchesMap.get(rel) || Object.create(null);
    for (const pattern of patterns) {
      const matches = matchesByPattern[pattern.id] || [];
      if (matches.length > 0) {
        const row = findings.get(pattern.id);
        row.total += matches.length;
        row.files.push({ file: rel, lines: matches });
      }
    }
  }
  for (const row of findings.values()) {
    row.files.sort((a, b) => a.file.localeCompare(b.file));
  }
  return {
    scannedFiles: files.map((f) => path.basename(f)),
    findings: Array.from(findings.values())
  };
}

function analyzeSessions({ memoryDir, patterns = PATTERNS, stopWhenAllMatched = false }) {
  const files = listMemoryFiles(memoryDir);
  const map = new Map();
  for (const filePath of files) {
    const rel = path.basename(filePath);
    map.set(rel, scanFileStreamSync(filePath, patterns, { stopWhenAllMatched }));
  }
  return aggregateFindings(files, patterns, map);
}

function serializePatterns(patterns) {
  return patterns.map((p) => ({
    id: p.id,
    title: p.title,
    recommendation: p.recommendation,
    source: p.regex.source,
    flags: p.regex.flags
  }));
}

function hydratePatterns(serialized) {
  return serialized.map((p) => ({
    id: p.id,
    title: p.title,
    recommendation: p.recommendation,
    regex: new RegExp(p.source, p.flags)
  }));
}

async function runWorkers(files, patterns, options = {}) {
  const workers = Math.max(1, Number(options.workers) || 1);
  const stopWhenAllMatched = Boolean(options.stopWhenAllMatched);
  const map = new Map();
  let index = 0;
  const encoded = serializePatterns(patterns);

  async function runSingle(filePath) {
    return new Promise((resolve, reject) => {
      const worker = new Worker(__filename, {
        workerData: {
          mode: 'scan_file',
          filePath,
          patterns: encoded,
          stopWhenAllMatched
        }
      });
      worker.once('message', (payload) => {
        resolve(payload);
      });
      worker.once('error', reject);
      worker.once('exit', (code) => {
        if (code !== 0) reject(new Error(`worker exited ${code}`));
      });
    });
  }

  async function loop() {
    while (true) {
      const i = index;
      index += 1;
      if (i >= files.length) return;
      const filePath = files[i];
      const payload = await runSingle(filePath);
      map.set(payload.file, payload.matchesByPattern);
    }
  }

  const pool = [];
  const size = Math.min(workers, files.length || 1);
  for (let i = 0; i < size; i += 1) {
    pool.push(loop());
  }
  await Promise.all(pool);
  return map;
}

async function analyzeSessionsConcurrent({ memoryDir, patterns = PATTERNS, workers = 2, stopWhenAllMatched = false }) {
  const files = listMemoryFiles(memoryDir);
  const fileMatchesMap = await runWorkers(files, patterns, { workers, stopWhenAllMatched });
  return aggregateFindings(files, patterns, fileMatchesMap);
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
  const out = { workers: 2, stopEarly: false };
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
    } else if (a === '--workers' && argv[i + 1]) {
      out.workers = Number.parseInt(argv[i + 1], 10);
      i += 1;
    } else if (a === '--stop-early') {
      out.stopEarly = true;
    }
  }
  return out;
}

async function main(argv = process.argv.slice(2)) {
  const args = parseArgs(argv);
  const repoRoot = resolveRepoRoot(process.cwd());
  const dateKey = args.date || utcDate();
  const memoryDir = args.memoryDir
    ? path.resolve(args.memoryDir)
    : path.join(repoRoot, 'workspace', 'memory');

  const workers = Math.max(1, Number(args.workers) || 1);
  const result = workers > 1
    ? await analyzeSessionsConcurrent({ memoryDir, workers, stopWhenAllMatched: args.stopEarly })
    : analyzeSessions({ memoryDir, stopWhenAllMatched: args.stopEarly });

  const outPath = writePatternReport({ repoRoot, dateKey, result, outPath: args.output });
  process.stdout.write(`${path.relative(repoRoot, outPath)}\n`);
}

if (!isMainThread && workerData && workerData.mode === 'scan_file') {
  try {
    const patterns = hydratePatterns(workerData.patterns || []);
    const rel = path.basename(workerData.filePath);
    const matchesByPattern = scanFileStreamSync(workerData.filePath, patterns, {
      stopWhenAllMatched: Boolean(workerData.stopWhenAllMatched)
    });
    parentPort.postMessage({ file: rel, matchesByPattern });
  } catch (error) {
    throw error;
  }
}

if (isMainThread && require.main === module) {
  main().catch((error) => {
    process.stderr.write(`analyze_session_patterns failed: ${error.message}\n`);
    process.exit(1);
  });
}

module.exports = {
  PATTERNS,
  analyzeSessions,
  analyzeSessionsConcurrent,
  renderReport,
  scanFileStreamSync,
  writePatternReport
};
