#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const { spawnSync } = require('node:child_process');

const LEGACY_RE = /\bSystem-1\b|\bSystem-2\b/;
const LEGACY_HEADER_RE = /Legacy Node Name Notice:/;

function parseAddedLegacyMentions(patchText) {
  const lines = String(patchText || '').split(/\r?\n/);
  const hits = [];
  let currentFile = null;

  for (const line of lines) {
    if (line.startsWith('+++ b/')) {
      currentFile = line.slice('+++ b/'.length).trim();
      continue;
    }
    if (!line.startsWith('+') || line.startsWith('+++')) {
      continue;
    }
    if (!currentFile) {
      continue;
    }
    const content = line.slice(1);
    if (LEGACY_RE.test(content)) {
      hits.push({ file: currentFile, line: content });
    }
  }

  return hits;
}

function hasLegacyHeader(filePath) {
  try {
    const content = fs.readFileSync(filePath, 'utf8');
    return LEGACY_HEADER_RE.test(content);
  } catch (_) {
    return false;
  }
}

function runDiff() {
  const result = spawnSync('git', ['diff', '--no-color', '--unified=0', '--', '.'], {
    encoding: 'utf8'
  });
  if (result.status !== 0) {
    throw new Error((result.stderr || '').trim() || 'git diff failed');
  }
  return result.stdout || '';
}

function lintLegacyNames(patchText) {
  const hits = parseAddedLegacyMentions(patchText);
  const violations = [];

  for (const hit of hits) {
    if (!hasLegacyHeader(hit.file)) {
      violations.push(hit);
    }
  }
  return violations;
}

function main() {
  const patchText = runDiff();
  const violations = lintLegacyNames(patchText);

  if (violations.length === 0) {
    console.log('[legacy-node-names] ok');
    return 0;
  }

  console.error('[legacy-node-names] violation: new legacy naming detected without header');
  for (const v of violations) {
    console.error(`  - ${v.file}: ${v.line}`);
  }
  console.error('Add "Legacy Node Name Notice:" to the file header before introducing System-1/System-2 labels.');
  return 1;
}

if (require.main === module) {
  process.exit(main());
}

module.exports = {
  parseAddedLegacyMentions,
  lintLegacyNames
};
