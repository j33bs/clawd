#!/usr/bin/env node

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

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

function readCommitEditMessage() {
  const gitDir = run('git rev-parse --git-dir') || '.git';
  const editMsgPath = path.join(process.cwd(), gitDir, 'COMMIT_EDITMSG');
  try {
    return fs.readFileSync(editMsgPath, 'utf8');
  } catch (error) {
    return '';
  }
}

function isAllowlistedPath(filePath) {
  if (filePath.startsWith('core/')) {
    return true;
  }

  if (
    filePath === '.gitignore' ||
    filePath === 'scripts/check_staged_allowlist.js' ||
    filePath === 'scripts/init_fallback_system.js' ||
    filePath === 'scripts/multi_agent_fallback.js' ||
    filePath === 'scripts/verify_model_routing.js' ||
    filePath === 'scripts/guarded_fs.js' ||
    filePath === 'MODEL_ROUTING.md' ||
    filePath === 'package.json'
  ) {
    return true;
  }

  if (filePath.startsWith('docs/design/')) {
    return true;
  }

  if (/^notes\/governance\/.*change-admission-gate.*\.md$/i.test(filePath)) {
    return true;
  }

  if (/^notes\/verification\/.*change-admission-gate.*\.md$/i.test(filePath)) {
    return true;
  }

  if (/^DESIGN_MODEL_ROUTER.*\.md$/.test(filePath)) {
    return true;
  }

  if (/^schemas\/.*event.*\.schema\.json$/.test(filePath)) {
    return true;
  }

  if (filePath.startsWith('tests/')) {
    return true;
  }

  return false;
}

function stableSortValue(value) {
  if (Array.isArray(value)) {
    return value.map(stableSortValue);
  }

  if (value && typeof value === 'object') {
    const result = {};
    Object.keys(value)
      .sort()
      .forEach((key) => {
        result[key] = stableSortValue(value[key]);
      });
    return result;
  }

  return value;
}

function stableStringify(value) {
  return JSON.stringify(stableSortValue(value));
}

function readGitJsonSpec(spec) {
  try {
    const content = execSync(`git show ${spec}`, {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore']
    });
    return JSON.parse(content);
  } catch (error) {
    return null;
  }
}

function isPackageJsonScriptsOnlyChange() {
  const stagedPkg = readGitJsonSpec(':package.json');
  if (!stagedPkg) {
    return false;
  }

  const headPkg = readGitJsonSpec('HEAD:package.json') || {};

  const headWithoutScripts = { ...headPkg };
  const stagedWithoutScripts = { ...stagedPkg };
  delete headWithoutScripts.scripts;
  delete stagedWithoutScripts.scripts;

  return stableStringify(headWithoutScripts) === stableStringify(stagedWithoutScripts);
}

function isRoutingOrGovernanceCommitContext(stagedFiles, commitMessage) {
  const fileTriggered = stagedFiles.some(
    (filePath) =>
      filePath.startsWith('core/') ||
      filePath === 'scripts/init_fallback_system.js' ||
      filePath === 'scripts/multi_agent_fallback.js'
  );

  const messageTriggered = /\[(ROUTER|GOV)\]/.test(commitMessage || '');
  return fileTriggered || messageTriggered;
}

function main() {
  if (process.env.ALLOW_EXTRA_FILES === '1') {
    console.log('[staged-allowlist] ALLOW_EXTRA_FILES=1 set, skipping enforcement.');
    return;
  }

  const stagedFiles = listStagedFiles();
  if (stagedFiles.length === 0) {
    return;
  }

  const commitMessage = readCommitEditMessage();
  if (!isRoutingOrGovernanceCommitContext(stagedFiles, commitMessage)) {
    return;
  }

  const offending = [];

  stagedFiles.forEach((filePath) => {
    if (!isAllowlistedPath(filePath)) {
      offending.push(filePath);
    }
  });

  if (stagedFiles.includes('package.json') && !isPackageJsonScriptsOnlyChange()) {
    offending.push('package.json (contains non-scripts staged changes)');
  }

  if (offending.length === 0) {
    return;
  }

  console.error('[staged-allowlist] violation: non-allowlisted staged files detected.');
  console.error('[staged-allowlist] Offending paths:');
  offending.forEach((filePath) => {
    console.error(`- ${filePath}`);
  });
  console.error('');
  console.error('[staged-allowlist] To override intentionally:');
  console.error('ALLOW_EXTRA_FILES=1 git commit ...');
  process.exit(1);
}

main();
