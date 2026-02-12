#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const { captureSnapshot } = require('./system2_snapshot_capture');
const { redactDirectory, DEFAULT_MAX_BYTES } = require('./redact_audit_evidence');

function parseArgs(argv) {
  const args = {
    outDir: null,
    maxBytes: DEFAULT_MAX_BYTES,
    maxLogLines: 500,
    json: false
  };

  for (let i = 0; i < argv.length; i += 1) {
    const tok = argv[i];

    if (tok === '--out' && i + 1 < argv.length) {
      args.outDir = argv[++i];
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

    if (tok === '--max-log-lines' && i + 1 < argv.length) {
      const parsed = Number(argv[++i]);
      if (!Number.isInteger(parsed) || parsed <= 0) {
        throw new Error('--max-log-lines must be a positive integer');
      }
      args.maxLogLines = parsed;
      continue;
    }

    if (tok === '--json') {
      args.json = true;
      continue;
    }

    throw new Error(`Unknown or incomplete argument: ${tok}`);
  }

  if (!args.outDir) {
    throw new Error('--out <dir> is required');
  }

  return args;
}

function sha256File(filePath) {
  const hash = crypto.createHash('sha256');
  hash.update(fs.readFileSync(filePath));
  return hash.digest('hex');
}

function collectFiles(dir) {
  const files = [];

  function walk(current) {
    let entries = [];
    try {
      entries = fs.readdirSync(current, { withFileTypes: true });
    } catch (_) {
      return;
    }

    entries.sort((a, b) => a.name.localeCompare(b.name));

    for (const entry of entries) {
      const fullPath = path.join(current, entry.name);
      if (entry.isDirectory()) {
        walk(fullPath);
        continue;
      }
      if (entry.isFile()) {
        files.push(fullPath);
      }
    }
  }

  walk(dir);
  files.sort();
  return files;
}

function buildManifest(redactedDir, outDir) {
  const files = collectFiles(redactedDir).map((fullPath) => {
    const relPath = path.relative(redactedDir, fullPath);
    const sizeBytes = fs.statSync(fullPath).size;
    return {
      path: relPath,
      size_bytes: sizeBytes,
      sha256: sha256File(fullPath)
    };
  });

  const manifest = {
    generated_at_utc: new Date().toISOString(),
    redacted_root: path.relative(process.cwd(), redactedDir) || '.',
    file_count: files.length,
    files
  };

  const manifestPath = path.join(outDir, 'manifest.json');
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n', 'utf8');

  return { manifestPath, manifest };
}

function buildEvidenceBundle(options) {
  const outDir = path.resolve(options.outDir);
  const rawDir = path.join(outDir, 'raw');
  const redactedDir = path.join(outDir, 'redacted');

  fs.rmSync(outDir, { recursive: true, force: true });
  fs.mkdirSync(rawDir, { recursive: true });
  fs.mkdirSync(redactedDir, { recursive: true });

  const snapshotResult = captureSnapshot({
    outDir: rawDir,
    maxLogLines: options.maxLogLines,
    runner: options.snapshotRunner
  });

  const redactionSummary = redactDirectory({
    inputDir: rawDir,
    outputDir: redactedDir,
    dryRun: false,
    json: false,
    maxBytes: options.maxBytes
  });

  const { manifestPath, manifest } = buildManifest(redactedDir, outDir);

  const summary = {
    timestamp_utc: new Date().toISOString(),
    out_dir: path.relative(process.cwd(), outDir) || '.',
    raw_dir: path.relative(process.cwd(), rawDir) || '.',
    redacted_dir: path.relative(process.cwd(), redactedDir) || '.',
    snapshot_ok: snapshotResult.ok,
    snapshot_summary: snapshotResult.summary,
    redaction_summary: {
      files_scanned: redactionSummary.files_scanned,
      files_written: redactionSummary.files_written,
      files_changed: redactionSummary.files_changed,
      files_skipped_too_large: redactionSummary.files_skipped_too_large,
      files_skipped_unreadable: redactionSummary.files_skipped_unreadable,
      files_skipped_invalid_json_after_redaction: redactionSummary.files_skipped_invalid_json_after_redaction,
      replacements_total: redactionSummary.replacements_total,
      pattern_counts: redactionSummary.pattern_counts
    },
    manifest_path: path.relative(process.cwd(), manifestPath) || manifestPath,
    manifest_file_count: manifest.file_count
  };

  return {
    ok: snapshotResult.ok,
    summary,
    manifest
  };
}

function main() {
  let args;

  try {
    args = parseArgs(process.argv.slice(2));
  } catch (error) {
    console.error(error.message);
    process.exit(2);
  }

  let result;
  try {
    result = buildEvidenceBundle(args);
  } catch (error) {
    console.error(`system2:evidence failed: ${error.message}`);
    process.exit(3);
  }

  console.log(JSON.stringify(result.summary, null, 2));

  if (!result.ok) {
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = {
  buildEvidenceBundle,
  parseArgs,
  buildManifest
};
