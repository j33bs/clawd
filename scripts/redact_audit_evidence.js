#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const SCRIPT_VERSION = '2.0.0';
const DEFAULT_MAX_BYTES = 10 * 1024 * 1024;

const ALLOWED_EXTENSIONS = new Set([
  '.md', '.txt', '.json', '.log', '.yml', '.yaml', '.csv', '.redacted'
]);

function parseArgs(argv) {
  const args = {
    inputDir: null,
    outputDir: null,
    dryRun: false,
    json: false,
    maxBytes: DEFAULT_MAX_BYTES
  };

  for (let i = 0; i < argv.length; i += 1) {
    const tok = argv[i];

    if (tok === '--in' && i + 1 < argv.length) {
      args.inputDir = argv[++i];
      continue;
    }

    if (tok === '--out' && i + 1 < argv.length) {
      args.outputDir = argv[++i];
      continue;
    }

    if (tok === '--dry-run') {
      args.dryRun = true;
      continue;
    }

    if (tok === '--json') {
      args.json = true;
      continue;
    }

    if (tok === '--max-bytes' && i + 1 < argv.length) {
      const parsed = Number(argv[++i]);
      if (!Number.isInteger(parsed) || parsed <= 0) {
        throw new Error('--max-bytes must be a positive integer');
      }
      args.maxBytes = parsed;
      continue;
    }

    throw new Error(`Unknown or incomplete argument: ${tok}`);
  }

  if (!args.inputDir || !args.outputDir) {
    throw new Error('Both --in <path> and --out <path> are required');
  }

  return args;
}

function isJsonFile(filePath) {
  return path.extname(filePath).toLowerCase() === '.json';
}

function validateJson(content) {
  try {
    JSON.parse(content);
    return true;
  } catch (_) {
    return false;
  }
}

function collectFiles(rootDir) {
  const files = [];

  function walk(dir) {
    let entries = [];
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch (_) {
      return;
    }

    entries.sort((a, b) => a.name.localeCompare(b.name));

    for (const entry of entries) {
      const full = path.join(dir, entry.name);

      if (entry.isDirectory()) {
        walk(full);
        continue;
      }

      if (!entry.isFile()) {
        continue;
      }

      if (!ALLOWED_EXTENSIONS.has(path.extname(entry.name).toLowerCase())) {
        continue;
      }

      files.push(full);
    }
  }

  walk(rootDir);
  files.sort();
  return files;
}

function buildRules() {
  return [
    {
      id: 'repo_root_path',
      pattern: /\/Users\/[A-Za-z0-9._-]+\/clawd\b/g,
      replacement: '{{REPO_ROOT}}'
    },
    {
      id: 'home_openclaw_path',
      pattern: /\/Users\/[A-Za-z0-9._-]+\/\.openclaw\b/g,
      replacement: '{{HOME}}/.openclaw'
    },
    {
      id: 'home_path_macos',
      pattern: /\/Users\/[A-Za-z0-9._-]+\b/g,
      replacement: '{{HOME}}'
    },
    {
      id: 'home_path_linux',
      pattern: /\/home\/[A-Za-z0-9._-]+\b/g,
      replacement: '{{HOME}}'
    },
    {
      id: 'email',
      pattern: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g,
      replacement: '{{EMAIL}}'
    },
    {
      id: 'openai_key_like',
      pattern: /\bsk-[A-Za-z0-9_-]{10,}\b/g,
      replacement: '{{SECRET_TOKEN}}'
    },
    {
      id: 'github_token_like',
      pattern: /\bgh[pousr]_[A-Za-z0-9]{20,}\b/g,
      replacement: '{{SECRET_TOKEN}}'
    },
    {
      id: 'bearer_token_like',
      pattern: /\bBearer\s+[A-Za-z0-9._-]{16,}\b/g,
      replacement: 'Bearer {{SECRET_TOKEN}}'
    },
    {
      id: 'internal_hostname',
      pattern: /\b(?:[A-Za-z0-9-]+\.)+(?:internal|local|lan|corp)\b/g,
      replacement: '{{HOST}}'
    },
    {
      id: 'ls_owner_group',
      pattern: /^([d\-lrwxsStT@+.]{10,}[@+.]?\s+\d+\s+)([A-Za-z0-9._-]+)(\s+)([A-Za-z0-9._-]+)(\s)/gm,
      replacement: '$1{{USER}}$3{{GROUP}}$5'
    },
    {
      id: 'username_literal',
      pattern: /\bheathyeager\b/g,
      replacement: '{{USER}}'
    }
  ];
}

function applyRules(content, rules) {
  let result = content;
  const counts = {};

  for (const rule of rules) {
    const before = result;
    result = result.replace(rule.pattern, rule.replacement);

    if (before === result) {
      counts[rule.id] = 0;
      continue;
    }

    const matches = before.match(rule.pattern);
    counts[rule.id] = matches ? matches.length : 0;
  }

  return { result, counts };
}

function redactDirectory(options) {
  const inputRoot = path.resolve(options.inputDir);
  const outputRoot = path.resolve(options.outputDir);

  if (!fs.existsSync(inputRoot) || !fs.statSync(inputRoot).isDirectory()) {
    throw new Error(`Input directory not found: ${options.inputDir}`);
  }

  const rules = buildRules();
  const files = collectFiles(inputRoot);

  const stats = {
    script_version: SCRIPT_VERSION,
    input_root: path.relative(process.cwd(), inputRoot) || '.',
    output_root: path.relative(process.cwd(), outputRoot) || '.',
    dry_run: options.dryRun,
    max_bytes: options.maxBytes,
    files_scanned: files.length,
    files_written: 0,
    files_changed: 0,
    files_skipped_too_large: 0,
    files_skipped_unreadable: 0,
    files_skipped_invalid_json_after_redaction: 0,
    replacements_total: 0,
    pattern_counts: {},
    changed_files: [],
    skipped_files: []
  };

  for (const rule of rules) {
    stats.pattern_counts[rule.id] = 0;
  }

  if (!options.dryRun) {
    fs.rmSync(outputRoot, { recursive: true, force: true });
    fs.mkdirSync(outputRoot, { recursive: true });
  }

  for (const fullPath of files) {
    const relPath = path.relative(inputRoot, fullPath);
    let fileStat;

    try {
      fileStat = fs.statSync(fullPath);
    } catch (_) {
      stats.files_skipped_unreadable += 1;
      stats.skipped_files.push({ file: relPath, reason: 'stat_failed' });
      continue;
    }

    if (fileStat.size > options.maxBytes) {
      stats.files_skipped_too_large += 1;
      stats.skipped_files.push({ file: relPath, reason: 'too_large' });
      continue;
    }

    let content;
    try {
      content = fs.readFileSync(fullPath, 'utf8');
    } catch (_) {
      stats.files_skipped_unreadable += 1;
      stats.skipped_files.push({ file: relPath, reason: 'read_failed' });
      continue;
    }

    const { result, counts } = applyRules(content, rules);

    if (isJsonFile(fullPath) && validateJson(content) && !validateJson(result)) {
      stats.files_skipped_invalid_json_after_redaction += 1;
      stats.skipped_files.push({ file: relPath, reason: 'invalid_json_after_redaction' });
      continue;
    }

    let fileReplacementCount = 0;
    for (const rule of rules) {
      const count = counts[rule.id] || 0;
      stats.pattern_counts[rule.id] += count;
      fileReplacementCount += count;
    }

    stats.replacements_total += fileReplacementCount;

    if (result !== content) {
      stats.files_changed += 1;
      stats.changed_files.push(relPath);
    }

    if (!options.dryRun) {
      const outPath = path.join(outputRoot, relPath);
      fs.mkdirSync(path.dirname(outPath), { recursive: true });
      fs.writeFileSync(outPath, result, 'utf8');
      stats.files_written += 1;
    }
  }

  stats.changed_files.sort();
  stats.skipped_files.sort((a, b) => a.file.localeCompare(b.file));

  return stats;
}

function usage() {
  return [
    'Usage:',
    '  node scripts/redact_audit_evidence.js --in <path> --out <path> [--dry-run] [--json] [--max-bytes <n>]',
    '',
    'Flags:',
    '  --in <path>       Input directory to scan and redact',
    '  --out <path>      Output directory for redacted bundle',
    '  --dry-run         Analyze and summarize without writing files',
    '  --json            Emit machine-readable JSON summary',
    '  --max-bytes <n>   Skip files larger than n bytes (default 10485760)'
  ].join('\n');
}

function main() {
  let args;

  try {
    args = parseArgs(process.argv.slice(2));
  } catch (err) {
    console.error(err.message);
    console.error('');
    console.error(usage());
    process.exit(2);
  }

  try {
    const summary = redactDirectory(args);

    if (args.json) {
      console.log(JSON.stringify(summary, null, 2));
      return;
    }

    console.log(`Scanned ${summary.files_scanned} file(s); changed ${summary.files_changed}; wrote ${summary.files_written}.`);
    if (summary.files_skipped_too_large > 0 || summary.files_skipped_unreadable > 0) {
      console.log(
        `Skipped too-large=${summary.files_skipped_too_large}, unreadable=${summary.files_skipped_unreadable}, invalid-json=${summary.files_skipped_invalid_json_after_redaction}.`
      );
    }
  } catch (err) {
    console.error(`Redaction failed: ${err.message}`);
    process.exit(3);
  }
}

if (require.main === module) {
  main();
}

module.exports = {
  ALLOWED_EXTENSIONS,
  DEFAULT_MAX_BYTES,
  SCRIPT_VERSION,
  applyRules,
  buildRules,
  parseArgs,
  redactDirectory,
  validateJson
};
