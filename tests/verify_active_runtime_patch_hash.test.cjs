#!/usr/bin/env node
'use strict';

const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { execSync } = require('node:child_process');

function resolveActivePackageDir() {
  const cliPath = execSync('which openclaw', { encoding: 'utf8' }).trim();
  assert.ok(cliPath, 'openclaw not found in PATH');
  const launcherPath = fs.realpathSync(cliPath);
  return path.dirname(launcherPath);
}

function sha256File(filePath) {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
}

function isAllowlisted(sha, allowlist) {
  return allowlist.allow.some((entry) => entry.sha256 === sha);
}

function main() {
  const activePackageDir = resolveActivePackageDir();
  const activeLoaderPath = path.join(activePackageDir, 'dist', 'loader-BAZoAqqR.js');
  assert.ok(fs.existsSync(activeLoaderPath), `active loader not found: ${activeLoaderPath}`);

  const allowlistPath = path.join(__dirname, '..', 'notes', 'governance', 'active_runtime_loader_hash_allowlist.json');
  assert.ok(fs.existsSync(allowlistPath), `allowlist not found: ${allowlistPath}`);

  const allowlist = JSON.parse(fs.readFileSync(allowlistPath, 'utf8'));
  assert.strictEqual(
    allowlist.activeLoaderBasename,
    'loader-BAZoAqqR.js',
    'allowlist activeLoaderBasename must match loader-BAZoAqqR.js'
  );

  const sha = sha256File(activeLoaderPath);
  const allowed = isAllowlisted(sha, allowlist);

  if (!allowed) {
    console.error('ACTIVE_LOADER=' + activeLoaderPath);
    console.error('COMPUTED_SHA256=' + sha);
    console.error("If this is an intentional OpenClaw upgrade, run the marker verifier first, then add this SHA to allowlist via the governed procedure in active_runtime_patch_verifier.md.");
  }

  assert.ok(allowed, 'active loader SHA is not in allowlist');

  const mutatedSha = `${sha.slice(0, -1)}${sha.endsWith('0') ? '1' : '0'}`;
  assert.ok(!isAllowlisted(mutatedSha, allowlist), 'mutated SHA should not be allowlisted');

  console.log('ACTIVE_LOADER=' + activeLoaderPath);
  console.log('COMPUTED_SHA256=' + sha);
  console.log('RESULT=PASS');
}

main();
