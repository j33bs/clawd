#!/usr/bin/env node

const { execSync } = require('child_process');
const fs = require('fs');

const SENSITIVE_PATHS = [
  /^core\//,
  /^scripts\/init_fallback_system\.js$/,
  /^scripts\/multi_agent_fallback\.js$/,
  /^scripts\/verify_model_routing\.js$/,
  /^scripts\/c_sim_funding_capture\.js$/,
  /^scripts\/check_staged_allowlist\.js$/,
  /^scripts\/check_change_admission_gate\.js$/,
  /^scripts\/hooks\/pre-commit$/,
  /^MODEL_ROUTING\.md$/
];

const GATE_DOC_PATTERNS = [
  /^notes\/verification\/.+change-admission-gate.*\.md$/i,
  /^notes\/governance\/.+change-admission-gate.*\.md$/i
];

const REQUIRED_SECTIONS = [
  'design brief',
  'evidence pack',
  'rollback plan',
  'budget envelope',
  'expected roi',
  'kill-switch',
  'post-mortem'
];

function run(command) {
  try {
    return execSync(command, {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore']
    }).trim();
  } catch (error) {
    return '';
  }
}

function listStagedFiles() {
  const output = run('git diff --cached --name-only');
  if (!output) {
    return [];
  }
  return output
    .split('\n')
    .map((value) => value.trim())
    .filter(Boolean);
}

function readStagedFile(filePath) {
  try {
    return execSync(`git show :${filePath}`, {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore']
    });
  } catch (error) {
    return null;
  }
}

function hasSensitiveChanges(stagedFiles) {
  return stagedFiles.some((filePath) => SENSITIVE_PATHS.some((pattern) => pattern.test(filePath)));
}

function listGateDocs(stagedFiles) {
  return stagedFiles.filter((filePath) => GATE_DOC_PATTERNS.some((pattern) => pattern.test(filePath)));
}

function contentHasRequiredSections(content) {
  if (!content) {
    return { ok: false, missing: REQUIRED_SECTIONS };
  }

  const lower = content.toLowerCase();
  const missing = REQUIRED_SECTIONS.filter((section) => !lower.includes(section));
  return { ok: missing.length === 0, missing };
}

function detectAutoRestartInSensitiveDiff(stagedFiles) {
  const offenders = [];

  stagedFiles.forEach((filePath) => {
    if (filePath === 'scripts/check_change_admission_gate.js') {
      return;
    }
    if (!SENSITIVE_PATHS.some((pattern) => pattern.test(filePath))) {
      return;
    }
    const diff = run(`git diff --cached --unified=0 -- ${filePath}`);
    if (!diff) {
      return;
    }
    const addedLines = diff
      .split('\n')
      .filter((line) => line.startsWith('+') && !line.startsWith('+++'))
      .join('\n')
      .toLowerCase();

    if (/auto[-_ ]?restart/.test(addedLines)) {
      offenders.push(filePath);
    }
  });

  return offenders;
}

function main() {
  if (process.env.ALLOW_EXTRA_FILES === '1') {
    console.log('[change-admission-gate] ALLOW_EXTRA_FILES=1 set, skipping enforcement.');
    return;
  }

  const stagedFiles = listStagedFiles();
  if (stagedFiles.length === 0) {
    return;
  }

  if (!hasSensitiveChanges(stagedFiles)) {
    return;
  }

  const gateDocs = listGateDocs(stagedFiles);
  if (gateDocs.length === 0) {
    console.error('[change-admission-gate] violation: sensitive changes require an admitted gate doc.');
    console.error('[change-admission-gate] Stage a gate record under:');
    console.error('- notes/verification/*change-admission-gate*.md');
    console.error('- notes/governance/*change-admission-gate*.md');
    console.error('');
    console.error('[change-admission-gate] Required sections:');
    REQUIRED_SECTIONS.forEach((section) => console.error(`- ${section}`));
    console.error('');
    console.error('[change-admission-gate] Override only if intentional: ALLOW_EXTRA_FILES=1 git commit ...');
    process.exit(1);
  }

  const sectionErrors = [];
  gateDocs.forEach((docPath) => {
    const content = readStagedFile(docPath);
    const sectionCheck = contentHasRequiredSections(content);
    if (!sectionCheck.ok) {
      sectionErrors.push({
        docPath,
        missing: sectionCheck.missing
      });
    }
  });

  if (sectionErrors.length > 0) {
    console.error('[change-admission-gate] violation: gate doc missing required sections.');
    sectionErrors.forEach((error) => {
      console.error(`- ${error.docPath}`);
      error.missing.forEach((section) => {
        console.error(`  - missing: ${section}`);
      });
    });
    process.exit(1);
  }

  const autoRestartOffenders = detectAutoRestartInSensitiveDiff(stagedFiles);
  if (autoRestartOffenders.length > 0) {
    console.error('[change-admission-gate] violation: auto-restart logic added in sensitive files.');
    autoRestartOffenders.forEach((filePath) => console.error(`- ${filePath}`));
    console.error('Kill-switch triggers must be terminal until redesign and new admitted change.');
    process.exit(1);
  }
}

main();
