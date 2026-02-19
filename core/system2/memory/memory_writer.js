'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { sanitizeContextInput } = require('../context_sanitizer');
const { resolveRepoRoot } = require('../security/integrity_guard');

function isoNow(tsUtcMs) {
  if (typeof tsUtcMs === 'number') return new Date(tsUtcMs).toISOString();
  return new Date().toISOString();
}

function utcDayKey(isoTs) {
  return String(isoTs).slice(0, 10);
}

function formatEntry({ tsUtc, source, text, redactions }) {
  const redactionSummary = redactions.length > 0
    ? redactions.map((x) => `${x.type}:${x.count}`).join(',')
    : 'none';
  return [
    `- ts_utc: ${tsUtc}`,
    `  source: ${source || 'unknown'}`,
    `  redactions: ${redactionSummary}`,
    '  text: |',
    ...String(text || '')
      .split('\n')
      .map((line) => `    ${line}`),
    ''
  ].join('\n');
}

function createMemoryWriter(opts = {}) {
  const repoRoot = resolveRepoRoot(opts.repoRoot || process.cwd());
  const memoryDir = path.join(repoRoot, 'workspace', 'memory');
  const reportsDir = path.join(repoRoot, 'workspace', 'reports');

  async function writeEntry(entry = {}) {
    const tsUtc = isoNow(entry.tsUtcMs);
    const day = utcDayKey(tsUtc);
    const target = path.join(memoryDir, `${day}.md`);

    const result = sanitizeContextInput(entry.text || '');
    const formatted = formatEntry({
      tsUtc,
      source: entry.source,
      text: result.sanitizedText,
      redactions: result.redactions
    });

    await fs.promises.mkdir(memoryDir, { recursive: true });
    await fs.promises.appendFile(target, formatted, 'utf8');

    if (result.redactions.length > 0) {
      await fs.promises.mkdir(reportsDir, { recursive: true });
      const reportPath = path.join(reportsDir, 'context_sanitizer.log');
      const line = JSON.stringify({
        ts_utc: tsUtc,
        source: entry.source || 'unknown',
        file: path.relative(repoRoot, target),
        redactions: result.redactions
      });
      await fs.promises.appendFile(reportPath, `${line}\n`, 'utf8');
    }

    return {
      path: target,
      tsUtc,
      redactions: result.redactions
    };
  }

  return {
    writeEntry
  };
}

module.exports = {
  createMemoryWriter
};
