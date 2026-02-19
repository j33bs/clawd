#!/usr/bin/env node
'use strict';

/**
 * Repo Index Generator (paths only)
 *
 * Generates:
 *  - docs/INDEX.md
 *  - docs/INDEX.json
 *
 * Safety:
 *  - Never reads file contents (paths only).
 *  - Skips growth-noise paths like docs/HANDOFFS/.
 */

import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

function getRepoRoot() {
  const res = spawnSync('git', ['rev-parse', '--show-toplevel'], { encoding: 'utf8' });
  if (res.status === 0) {
    const p = String(res.stdout || '').trim();
    if (p) return p;
  }
  return process.cwd();
}

const IGNORE_DIR_NAMES = new Set([
  '.git',
  'node_modules',
  'dist',
  'build',
  'coverage',
  '.cache',
  '.tmp',
  '.venv',
  'venv',
  '__pycache__',
  '.mypy_cache',
  '.pytest_cache'
]);

const IGNORE_PATH_PREFIXES = [
  path.join('docs', 'HANDOFFS') + path.sep
];

function shouldIgnoreRelPath(relPath) {
  const norm = relPath.split(path.sep).join(path.sep);
  for (const prefix of IGNORE_PATH_PREFIXES) {
    if (norm.startsWith(prefix)) return true;
  }
  return false;
}

function walkPaths(repoRoot) {
  const out = [];

  /** @type {string[]} */
  const stack = ['.'];
  while (stack.length > 0) {
    const rel = stack.pop();
    if (!rel) break;

    if (rel !== '.' && shouldIgnoreRelPath(rel + path.sep)) {
      continue;
    }

    const abs = path.join(repoRoot, rel);
    let entries;
    try {
      entries = fs.readdirSync(abs, { withFileTypes: true });
    } catch (_) {
      continue;
    }

    for (const ent of entries) {
      const name = ent.name;
      if (!name) continue;
      if (name === '.DS_Store') continue;

      const childRel = rel === '.' ? name : path.join(rel, name);

      if (ent.isDirectory()) {
        if (IGNORE_DIR_NAMES.has(name)) continue;
        if (shouldIgnoreRelPath(childRel + path.sep)) continue;
        stack.push(childRel);
        continue;
      }

      if (shouldIgnoreRelPath(childRel)) continue;
      out.push(childRel.split(path.sep).join('/'));
    }
  }

  out.sort();
  return out;
}

function dirSummary(files) {
  const counts = new Map();
  for (const f of files) {
    const top = f.split('/')[0] || f;
    counts.set(top, (counts.get(top) || 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => a[0].localeCompare(b[0]));
}

function main() {
  const repoRoot = getRepoRoot();
  const files = walkPaths(repoRoot);

  const highlights = [
    'openclaw.json',
    'core/system2/inference/router.js',
    'core/system2/inference/provider_registry.js',
    'core/system2/inference/catalog.js',
    'core/system2/inference/secrets_bridge.js'
  ].map((p) => ({
    path: p,
    exists: fs.existsSync(path.join(repoRoot, p))
  }));

  const indexJson = {
    version: 1,
    highlights,
    counts: {
      total_files: files.length
    },
    top_level: dirSummary(files).map(([name, count]) => ({ name, count })),
    files
  };

  const docsDir = path.join(repoRoot, 'docs');
  if (!fs.existsSync(docsDir)) {
    fs.mkdirSync(docsDir, { recursive: true });
  }

  const outJsonPath = path.join(docsDir, 'INDEX.json');
  fs.writeFileSync(outJsonPath, JSON.stringify(indexJson, null, 2) + '\n', 'utf8');

  const mdLines = [];
  mdLines.push('# Repo Index');
  mdLines.push('');
  mdLines.push('Highlights (navigation anchors):');
  for (const h of highlights) {
    const status = h.exists ? 'ok' : 'missing';
    mdLines.push(`- \`${h.path}\` (${status})`);
  }
  mdLines.push('');
  mdLines.push(`Total files indexed (paths only): **${files.length}**`);
  mdLines.push('');
  mdLines.push('Top-level path counts:');
  for (const row of indexJson.top_level) {
    mdLines.push(`- \`${row.name}\`: ${row.count}`);
  }
  mdLines.push('');
  mdLines.push('Notes:');
  mdLines.push('- This index is paths-only (no content reads).');
  mdLines.push('- `docs/HANDOFFS/` is excluded from the file list to avoid growth noise.');
  mdLines.push('- Full path inventory is in `docs/INDEX.json`.');
  mdLines.push('');

  const outMdPath = path.join(docsDir, 'INDEX.md');
  fs.writeFileSync(outMdPath, mdLines.join('\n') + '\n', 'utf8');

  // Output paths for operator tooling
  process.stdout.write(`wrote ${path.relative(repoRoot, outMdPath)}\n`);
  process.stdout.write(`wrote ${path.relative(repoRoot, outJsonPath)}\n`);
}

main();

