#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const DEFAULT_IGNORED_PATHS = [
  'timestamp_utc',
  'snapshot_summary.timestamp_utc'
];

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
    aPath: null,
    bPath: null,
    json: false,
    ignore: [],
    failOn: []
  };

  for (let i = 0; i < argv.length; i += 1) {
    const tok = argv[i];

    if (tok === '--a' && i + 1 < argv.length) {
      args.aPath = argv[++i];
      continue;
    }

    if (tok === '--b' && i + 1 < argv.length) {
      args.bPath = argv[++i];
      continue;
    }

    if (tok === '--json') {
      args.json = true;
      continue;
    }

    if (tok === '--ignore' && i + 1 < argv.length) {
      args.ignore = parseList(argv[++i]);
      continue;
    }

    if (tok === '--fail-on' && i + 1 < argv.length) {
      args.failOn = parseList(argv[++i]);
      continue;
    }

    throw new Error(`Unknown or incomplete argument: ${tok}`);
  }

  if (!args.aPath || !args.bPath) {
    throw new Error('Both --a <file> and --b <file> are required');
  }

  return args;
}

function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function flattenObject(value, prefix, out, depth, maxDepth) {
  if (Array.isArray(value)) {
    out[prefix] = JSON.stringify(value);
    return;
  }

  if (!isPlainObject(value) || depth >= maxDepth) {
    out[prefix] = isPlainObject(value) ? JSON.stringify(value) : value;
    return;
  }

  const keys = Object.keys(value).sort();
  for (const key of keys) {
    const nextPrefix = prefix ? `${prefix}.${key}` : key;
    flattenObject(value[key], nextPrefix, out, depth + 1, maxDepth);
  }
}

function flattenForDiff(value, maxDepth = 32) {
  const out = {};
  if (!isPlainObject(value)) {
    out.value = Array.isArray(value) ? JSON.stringify(value) : value;
    return out;
  }
  const keys = Object.keys(value).sort();
  for (const key of keys) {
    flattenObject(value[key], key, out, 1, maxDepth);
  }
  return out;
}

function loadJson(filePath) {
  const raw = fs.readFileSync(filePath, 'utf8');
  return JSON.parse(raw);
}

function toNumberOrNull(value) {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return null;
}

function computeDiff(aObj, bObj, options = {}) {
  const ignoredSet = new Set([...(options.ignore || [])]);
  const failOnSet = new Set(options.failOn || []);

  const flatA = flattenForDiff(aObj, options.maxDepth || 32);
  const flatB = flattenForDiff(bObj, options.maxDepth || 32);

  const keys = new Set([...Object.keys(flatA), ...Object.keys(flatB)]);
  const changed = [];
  const added = [];
  const removed = [];
  const regressions = [];

  for (const key of Array.from(keys).sort()) {
    if (ignoredSet.has(key)) {
      continue;
    }

    const hasA = Object.prototype.hasOwnProperty.call(flatA, key);
    const hasB = Object.prototype.hasOwnProperty.call(flatB, key);

    if (hasA && hasB) {
      const aVal = flatA[key];
      const bVal = flatB[key];
      if (!Object.is(aVal, bVal)) {
        changed.push({ path: key, a: aVal, b: bVal });

        if (failOnSet.has(key)) {
          const aNum = toNumberOrNull(aVal);
          const bNum = toNumberOrNull(bVal);
          if (aNum !== null && bNum !== null && bNum > aNum) {
            regressions.push({ path: key, a: aNum, b: bNum });
          }
        }
      }
      continue;
    }

    if (!hasA && hasB) {
      added.push({ path: key, b: flatB[key] });
      continue;
    }

    if (hasA && !hasB) {
      removed.push({ path: key, a: flatA[key] });
    }
  }

  return {
    ignored: Array.from(ignoredSet).sort(),
    changed,
    added,
    removed,
    regressions
  };
}

function summarizeHuman(diff) {
  const lines = [];
  lines.push(
    `changed=${diff.changed.length} added=${diff.added.length} removed=${diff.removed.length} regressions=${diff.regressions.length}`
  );

  for (const entry of diff.changed.slice(0, 10)) {
    lines.push(`CHANGED ${entry.path}: ${JSON.stringify(entry.a)} -> ${JSON.stringify(entry.b)}`);
  }
  for (const entry of diff.added.slice(0, 10)) {
    lines.push(`ADDED ${entry.path}: ${JSON.stringify(entry.b)}`);
  }
  for (const entry of diff.removed.slice(0, 10)) {
    lines.push(`REMOVED ${entry.path}: ${JSON.stringify(entry.a)}`);
  }
  if (diff.regressions.length > 0) {
    lines.push('REGRESSION');
    for (const entry of diff.regressions) {
      lines.push(`REGRESSION ${entry.path}: ${entry.a} -> ${entry.b}`);
    }
  }

  return lines.join('\n');
}

function main() {
  try {
    const args = parseArgs(process.argv.slice(2));
    const aAbs = path.resolve(args.aPath);
    const bAbs = path.resolve(args.bPath);

    const aObj = loadJson(aAbs);
    const bObj = loadJson(bAbs);

    const ignored = [...DEFAULT_IGNORED_PATHS, ...args.ignore];
    const diff = computeDiff(aObj, bObj, {
      ignore: ignored,
      failOn: args.failOn
    });

    const output = {
      a: args.aPath,
      b: args.bPath,
      ignored: diff.ignored,
      changed: diff.changed,
      added: diff.added,
      removed: diff.removed,
      regressions: diff.regressions
    };

    if (args.json) {
      console.log(JSON.stringify(output, null, 2));
    } else {
      console.log(summarizeHuman(output));
    }

    const hasDiff = output.changed.length > 0 || output.added.length > 0 || output.removed.length > 0;
    if (hasDiff) {
      process.exit(2);
    }
  } catch (error) {
    console.error(`system2:diff failed: ${error.message}`);
    process.exit(3);
  }
}

if (require.main === module) {
  main();
}

module.exports = {
  DEFAULT_IGNORED_PATHS,
  computeDiff,
  flattenForDiff,
  parseArgs
};
