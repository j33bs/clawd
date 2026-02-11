#!/usr/bin/env node
'use strict';

/**
 * redact_audit_evidence.js
 *
 * Deterministic, idempotent redaction of host-identifying paths and usernames
 * from audit evidence artifacts. Designed for CBP-governed repos going public.
 *
 * Usage:
 *   node scripts/redact_audit_evidence.js --dry-run [--root <path>]
 *   node scripts/redact_audit_evidence.js --apply  [--root <path>] [--report <path>]
 *
 * Replacements (applied in this order):
 *   /Users/<name>/clawd        -> {{REPO_ROOT}}
 *   /Users/<name>/.openclaw    -> {{HOME}}/.openclaw
 *   /Users/<name>              -> {{HOME}}
 *   heathyeager (standalone)   -> {{USER}}
 *   ls -la owner/group columns -> {{USER}} {{GROUP}}
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const SCRIPT_VERSION = '1.0.0';

const ALLOWED_EXTENSIONS = new Set([
  '.md', '.txt', '.json', '.log', '.yml', '.yaml', '.csv', '.redacted'
]);

const MAX_FILE_BYTES = 10 * 1024 * 1024; // 10 MB safety limit

// ---------- argument parsing ----------

function parseArgs(argv) {
  const args = { dryRun: false, apply: false, root: null, report: null };
  for (let i = 0; i < argv.length; i += 1) {
    const tok = argv[i];
    if (tok === '--dry-run') { args.dryRun = true; continue; }
    if (tok === '--apply') { args.apply = true; continue; }
    if (tok === '--root' && i + 1 < argv.length) { args.root = argv[++i]; continue; }
    if (tok === '--report' && i + 1 < argv.length) { args.report = argv[++i]; continue; }
  }
  return args;
}

// ---------- file walker ----------

function walkDir(dir, sink) {
  let entries;
  try { entries = fs.readdirSync(dir, { withFileTypes: true }); }
  catch (_) { return; }
  for (const ent of entries) {
    const full = path.join(dir, ent.name);
    if (ent.isDirectory()) { walkDir(full, sink); continue; }
    if (ent.isFile()) {
      const ext = path.extname(ent.name).toLowerCase();
      if (ALLOWED_EXTENSIONS.has(ext)) { sink.push(full); }
    }
  }
}

// ---------- replacement engine ----------

/**
 * Ordered list of replacement rules.
 * Order matters: longer/more-specific paths must be replaced before shorter ones.
 */
function buildRules() {
  return [
    // 1) /Users/<name>/clawd/... -> {{REPO_ROOT}}/...
    {
      id: 'repo_root_path',
      pattern: /\/Users\/[a-zA-Z0-9._-]+\/clawd\b/g,
      replacement: '{{REPO_ROOT}}'
    },
    // 2) /Users/<name>/.openclaw -> {{HOME}}/.openclaw
    {
      id: 'home_openclaw_path',
      pattern: /\/Users\/[a-zA-Z0-9._-]+\/\.openclaw/g,
      replacement: '{{HOME}}/.openclaw'
    },
    // 3) /Users/<name> (remaining) -> {{HOME}}
    {
      id: 'home_path',
      pattern: /\/Users\/[a-zA-Z0-9._-]+/g,
      replacement: '{{HOME}}'
    },
    // 4) ls -la style owner/group columns: "heathyeager  staff" or "heathyeager  heathyeager"
    //    Match pattern: <permissions> <linkcount> <owner> <group>
    //    e.g. "drwxr-xr-x@ 12 heathyeager  staff"
    {
      id: 'ls_owner_group',
      pattern: /^([d\-lrwxsStT@+.]{10,}[@+.]?\s+\d+\s+)heathyeager(\s+)(staff|heathyeager|wheel|admin)(\s)/gm,
      replacement: '$1{{USER}}$2{{GROUP}}$4'
    },
    // 5) Standalone username token "heathyeager" (remaining occurrences)
    {
      id: 'username',
      pattern: /heathyeager/g,
      replacement: '{{USER}}'
    }
  ];
}

function applyRules(content, rules) {
  let result = content;
  const counts = {};
  for (const rule of rules) {
    counts[rule.id] = 0;
    // Reset lastIndex for global regexes (they're recreated per buildRules call,
    // but guard against reuse)
    if (rule.pattern.global) { rule.pattern.lastIndex = 0; }
    // Count matches first, then do the replacement with the string replacement
    // (which handles $1/$2 back-references natively in String.replace)
    const before = result;
    result = result.replace(rule.pattern, rule.replacement);
    if (result !== before) {
      // Count actual replacements by running the regex on the original
      const matches = before.match(rule.pattern);
      counts[rule.id] = matches ? matches.length : 0;
    }
  }
  return { result, counts };
}

// ---------- JSON safety ----------

function isJsonFile(filePath) {
  return path.extname(filePath).toLowerCase() === '.json';
}

function validateJson(content) {
  try { JSON.parse(content); return true; }
  catch (_) { return false; }
}

// ---------- main logic ----------

function run(args) {
  const repoRoot = path.resolve(args.root || path.join(process.cwd(), 'workspace', 'docs', 'audits'));
  const rules = buildRules();
  const files = [];
  walkDir(repoRoot, files);
  files.sort();

  const stats = {
    scriptVersion: SCRIPT_VERSION,
    scriptHash: null,
    root: repoRoot,
    mode: args.apply ? 'apply' : 'dry-run',
    ts: new Date().toISOString(),
    totalFilesScanned: files.length,
    filesChanged: 0,
    filesSkippedBinary: 0,
    filesSkippedSize: 0,
    filesSkippedJsonInvalid: 0,
    patternCounts: {},
    changedFiles: [],
    skippedFiles: [],
    sampleLines: []
  };

  // Compute script hash
  try {
    const scriptContent = fs.readFileSync(path.join(process.cwd(), 'scripts', 'redact_audit_evidence.js'), 'utf8');
    stats.scriptHash = crypto.createHash('sha256').update(scriptContent).digest('hex');
  } catch (_) {
    stats.scriptHash = 'unknown';
  }

  // Initialize pattern counters
  for (const rule of rules) {
    stats.patternCounts[rule.id] = 0;
  }

  for (const filePath of files) {
    const relPath = path.relative(process.cwd(), filePath);

    // Size check
    let fileStat;
    try { fileStat = fs.statSync(filePath); }
    catch (_) { stats.skippedFiles.push({ path: relPath, reason: 'stat_failed' }); continue; }
    if (fileStat.size > MAX_FILE_BYTES) {
      stats.filesSkippedSize += 1;
      stats.skippedFiles.push({ path: relPath, reason: 'too_large' });
      continue;
    }

    // Read as UTF-8
    let content;
    try { content = fs.readFileSync(filePath, 'utf8'); }
    catch (_) {
      stats.filesSkippedBinary += 1;
      stats.skippedFiles.push({ path: relPath, reason: 'read_failed' });
      continue;
    }

    // Apply rules
    const { result, counts } = applyRules(content, rules);

    const totalReplacements = Object.values(counts).reduce((a, b) => a + b, 0);
    if (totalReplacements === 0) { continue; }

    // JSON validity check: only skip if the file was valid JSON before redaction
    // and redaction broke it. If it was already invalid, redact it as plain text.
    if (isJsonFile(filePath)) {
      const wasValidBefore = validateJson(content);
      const isValidAfter = validateJson(result);
      if (wasValidBefore && !isValidAfter) {
        stats.filesSkippedJsonInvalid += 1;
        stats.skippedFiles.push({ path: relPath, reason: 'json_valid_before_invalid_after' });
        continue;
      }
      // Track files that were already invalid (informational only, still redact)
      if (!wasValidBefore) {
        stats.skippedFiles.push({ path: relPath, reason: 'json_already_invalid_redacted_as_text' });
      }
    }

    // Accumulate stats
    for (const rule of rules) {
      stats.patternCounts[rule.id] += counts[rule.id];
    }
    stats.filesChanged += 1;
    stats.changedFiles.push(relPath);

    // Collect sample lines (up to 20 total)
    if (stats.sampleLines.length < 20) {
      const origLines = content.split('\n');
      const newLines = result.split('\n');
      for (let i = 0; i < origLines.length && stats.sampleLines.length < 20; i += 1) {
        if (origLines[i] !== newLines[i]) {
          stats.sampleLines.push({
            file: relPath,
            line: i + 1,
            before: origLines[i].slice(0, 200),
            after: newLines[i].slice(0, 200)
          });
        }
      }
    }

    // Write if applying
    if (args.apply) {
      fs.writeFileSync(filePath, result, 'utf8');
    }
  }

  return stats;
}

// ---------- report generator ----------

function generateMarkdownReport(stats) {
  const lines = [];
  lines.push('# Audit Evidence Redaction Report');
  lines.push('');
  lines.push(`**Date:** ${stats.ts}`);
  lines.push(`**Mode:** ${stats.mode}`);
  lines.push(`**Script version:** ${stats.scriptVersion}`);
  lines.push(`**Script SHA-256:** \`${stats.scriptHash}\``);
  lines.push(`**Root scanned:** \`${stats.root}\``);
  lines.push('');
  lines.push('## Summary');
  lines.push('');
  lines.push(`| Metric | Count |`);
  lines.push(`|--------|-------|`);
  lines.push(`| Files scanned | ${stats.totalFilesScanned} |`);
  lines.push(`| Files changed | ${stats.filesChanged} |`);
  lines.push(`| Files skipped (binary/read error) | ${stats.filesSkippedBinary} |`);
  lines.push(`| Files skipped (too large) | ${stats.filesSkippedSize} |`);
  lines.push(`| Files skipped (JSON invalid after redaction) | ${stats.filesSkippedJsonInvalid} |`);
  lines.push('');
  lines.push('## Patterns Redacted');
  lines.push('');
  lines.push('| Pattern ID | Replacement | Count |');
  lines.push('|------------|-------------|-------|');
  for (const [id, count] of Object.entries(stats.patternCounts)) {
    const rule = buildRules().find((r) => r.id === id);
    const repl = rule ? rule.replacement.replace(/\$/g, '\\$') : '?';
    lines.push(`| \`${id}\` | \`${repl}\` | ${count} |`);
  }
  lines.push('');
  lines.push('## Changed Files');
  lines.push('');
  for (const f of stats.changedFiles) {
    lines.push(`- \`${f}\``);
  }
  lines.push('');
  if (stats.skippedFiles.length > 0) {
    lines.push('## Skipped Files');
    lines.push('');
    for (const s of stats.skippedFiles) {
      lines.push(`- \`${s.path}\`: ${s.reason}`);
    }
    lines.push('');
  }
  lines.push('## Sample Lines (before/after)');
  lines.push('');
  for (const sample of stats.sampleLines) {
    lines.push(`### \`${sample.file}\` line ${sample.line}`);
    lines.push('');
    lines.push('**Before:**');
    lines.push('```');
    lines.push(sample.before);
    lines.push('```');
    lines.push('**After:**');
    lines.push('```');
    lines.push(sample.after);
    lines.push('```');
    lines.push('');
  }
  lines.push('## Verification Steps');
  lines.push('');
  lines.push('```bash');
  lines.push('# Confirm zero remaining occurrences:');
  lines.push("# Search for any remaining absolute home-directory paths or usernames:");
  lines.push("grep -rIE '/(Us)ers/[a-zA-Z]' workspace/docs/audits/ | wc -l  # expect 0");
  lines.push("grep -rI '{{USER}}' workspace/docs/audits/ | wc -l             # expect 0  (username was redacted)");
  lines.push('');
  lines.push('# Confirm JSON validity:');
  lines.push("find workspace/docs/audits -name '*.json' -exec node -e 'JSON.parse(require(\"fs\").readFileSync(process.argv[1],\"utf8\"))' {} \\;");
  lines.push('');
  lines.push('# Revert if needed:');
  lines.push('git revert <commit-sha>');
  lines.push('```');
  lines.push('');
  return lines.join('\n');
}

function generateManifest(stats) {
  const lines = [];
  lines.push('# Redaction Manifest');
  lines.push(`timestamp=${stats.ts}`);
  lines.push(`script_version=${stats.scriptVersion}`);
  lines.push(`script_sha256=${stats.scriptHash}`);
  lines.push(`mode=${stats.mode}`);
  lines.push(`command=node scripts/redact_audit_evidence.js --apply --report workspace/docs/audits/REDACTION-REPORT-2026-02-12.md`);
  lines.push('');
  lines.push('# Replacement counts per pattern');
  for (const [id, count] of Object.entries(stats.patternCounts)) {
    lines.push(`${id}=${count}`);
  }
  lines.push('');
  lines.push(`total_files_scanned=${stats.totalFilesScanned}`);
  lines.push(`files_changed=${stats.filesChanged}`);
  lines.push('');
  lines.push('# Changed files (relative to repo root)');
  for (const f of stats.changedFiles) {
    lines.push(f);
  }
  lines.push('');
  return lines.join('\n');
}

// ---------- entrypoint ----------

function main() {
  const args = parseArgs(process.argv.slice(2));

  if (!args.dryRun && !args.apply) {
    console.error('Usage: node scripts/redact_audit_evidence.js --dry-run|--apply [--root <path>] [--report <path>]');
    process.exit(2);
  }

  const stats = run(args);

  // Write report if --report specified
  if (args.report && args.apply) {
    const reportPath = path.resolve(args.report);
    fs.mkdirSync(path.dirname(reportPath), { recursive: true });
    let reportContent = generateMarkdownReport(stats);
    // Self-redact the report: it contains raw paths in stats.root and sample "before" lines
    const selfRules = buildRules();
    const { result: redactedReport } = applyRules(reportContent, selfRules);
    fs.writeFileSync(reportPath, redactedReport, 'utf8');
    console.error(`Report written: ${args.report}`);
  }

  // Write manifest if applying
  if (args.apply) {
    const manifestDir = path.join(
      process.cwd(), 'workspace', 'docs', 'audits',
      'SYSTEM2-EVIDENCE-2026-02-11', 'postfix_rce'
    );
    const manifestPath = path.join(manifestDir, 'redaction_manifest.txt');
    fs.mkdirSync(manifestDir, { recursive: true });
    let manifestContent = generateManifest(stats);
    // Self-redact the manifest too
    const selfRules2 = buildRules();
    const { result: redactedManifest } = applyRules(manifestContent, selfRules2);
    fs.writeFileSync(manifestPath, redactedManifest, 'utf8');
    console.error(`Manifest written: ${path.relative(process.cwd(), manifestPath)}`);
  }

  // Always emit JSON stats to stdout
  console.log(JSON.stringify(stats, null, 2));
}

if (require.main === module) {
  main();
}

module.exports = {
  applyRules,
  buildRules,
  validateJson,
  ALLOWED_EXTENSIONS,
  SCRIPT_VERSION
};
