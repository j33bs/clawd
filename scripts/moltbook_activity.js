#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

function isEnabled(env = process.env) {
  return String(env.OPENCLAW_ENABLE_MOLTBOOK_TRACKER || '0') === '1';
}

function parseJsonl(filePath) {
  if (!fs.existsSync(filePath)) return [];
  const lines = fs.readFileSync(filePath, 'utf8').split(/\r?\n/).filter(Boolean);
  const out = [];
  for (const line of lines) {
    try {
      out.push(JSON.parse(line));
    } catch (_) {}
  }
  return out;
}

function monthKeyFromTs(tsUtc) {
  const iso = new Date(tsUtc).toISOString();
  return iso.slice(0, 7);
}

function buildMonthlyImpact(entries, targetMonth) {
  const month = targetMonth || new Date().toISOString().slice(0, 7);
  const out = {
    month,
    posts: 0,
    likes: 0,
    comments: 0,
    shares: 0,
    engagements_total: 0
  };
  for (const entry of entries) {
    if (!entry || !entry.ts_utc) continue;
    if (monthKeyFromTs(entry.ts_utc) !== month) continue;
    out.posts += Number(entry.posts || 0);
    out.likes += Number(entry.likes || 0);
    out.comments += Number(entry.comments || 0);
    out.shares += Number(entry.shares || 0);
  }
  out.engagements_total = out.likes + out.comments + out.shares;
  return out;
}

function writeMonthlyReport(repoRoot, report) {
  const reportsDir = path.join(repoRoot, 'workspace', 'reports');
  fs.mkdirSync(reportsDir, { recursive: true });
  const outPath = path.join(reportsDir, `moltbook-impact-${report.month}.md`);
  const lines = [
    '# Moltbook Monthly Impact',
    '',
    `- month: ${report.month}`,
    `- posts: ${report.posts}`,
    `- likes: ${report.likes}`,
    `- comments: ${report.comments}`,
    `- shares: ${report.shares}`,
    `- engagements_total: ${report.engagements_total}`,
    ''
  ];
  fs.writeFileSync(outPath, `${lines.join('\n')}\n`, 'utf8');
  return outPath;
}

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--input' && argv[i + 1]) {
      out.input = argv[i + 1];
      i += 1;
    } else if (arg === '--month' && argv[i + 1]) {
      out.month = argv[i + 1];
      i += 1;
    } else if (arg === '--fetch-url' && argv[i + 1]) {
      out.fetchUrl = argv[i + 1];
      i += 1;
    }
  }
  return out;
}

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

function main() {
  const env = process.env;
  if (!isEnabled(env)) {
    process.stdout.write('disabled: set OPENCLAW_ENABLE_MOLTBOOK_TRACKER=1\n');
    return;
  }

  const args = parseArgs(process.argv.slice(2));
  if (args.fetchUrl && String(env.OPENCLAW_ENABLE_MOLTBOOK_NETWORK || '0') !== '1') {
    throw new Error('network ingestion is disabled; use local stub input or set OPENCLAW_ENABLE_MOLTBOOK_NETWORK=1 explicitly');
  }

  const repoRoot = resolveRepoRoot(process.cwd());
  const inputPath = args.input
    ? path.resolve(args.input)
    : path.join(repoRoot, 'workspace', 'memory', 'moltbook_activity_stub.jsonl');
  const entries = parseJsonl(inputPath);
  const report = buildMonthlyImpact(entries, args.month);
  const outPath = writeMonthlyReport(repoRoot, report);
  process.stdout.write(`${path.relative(repoRoot, outPath)}\n`);
}

if (require.main === module) {
  try {
    main();
  } catch (error) {
    process.stderr.write(`moltbook_activity failed: ${error.message}\n`);
    process.exit(1);
  }
}

module.exports = {
  isEnabled,
  parseJsonl,
  buildMonthlyImpact,
  writeMonthlyReport
};
