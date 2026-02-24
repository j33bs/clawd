'use strict';

const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { decide } = require('../core/system2/security/tool_governance');

function testAllowlistAction() {
  const out = decide({ action: 'read_status' }, { trustLevel: 'untrusted' }, { repoRoot: '/tmp/repo' });
  assert.strictEqual(out.decision, 'allow');
  console.log('PASS tool governance allows explicit allowlist actions');
}

function testAskThresholds() {
  const execOut = decide({ action: 'spawn_child_process' }, { trustLevel: 'trusted' }, { repoRoot: '/tmp/repo' });
  assert.strictEqual(execOut.decision, 'ask');

  const netOut = decide({ action: 'gateway_rpc_broad' }, { trustLevel: 'untrusted' }, { repoRoot: '/tmp/repo' });
  assert.strictEqual(netOut.decision, 'ask');

  const fsOut = decide(
    { action: 'fs_write_outside_repo', targetPath: '/etc/hosts' },
    { trustLevel: 'untrusted' },
    { repoRoot: '/tmp/repo' }
  );
  assert.strictEqual(fsOut.decision, 'ask');
  console.log('PASS tool governance asks for exec/network/outside-workspace writes');
}

function testDenylistAction() {
  const out = decide({ action: 'policy_bypass_override' }, { trustLevel: 'trusted' }, { repoRoot: '/tmp/repo' });
  assert.strictEqual(out.decision, 'deny');
  console.log('PASS tool governance denies explicit denylist actions');
}

function testWorkspaceBoundaryPrefixAndTraversalChecks() {
  const repoRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'tool-governance-'));
  fs.mkdirSync(path.join(repoRoot, 'workspace'), { recursive: true });
  fs.mkdirSync(path.join(repoRoot, 'workspace_evil'), { recursive: true });

  const inside = decide(
    { action: 'fs_write_outside_repo', targetPath: path.join(repoRoot, 'workspace', 'safe.txt') },
    { trustLevel: 'untrusted' },
    { repoRoot }
  );
  assert.strictEqual(inside.decision, 'allow');

  const prefixBypass = decide(
    { action: 'fs_write_outside_repo', targetPath: path.join(repoRoot, 'workspace_evil', 'pwn.txt') },
    { trustLevel: 'untrusted' },
    { repoRoot }
  );
  assert.strictEqual(prefixBypass.decision, 'ask');
  console.log('PASS tool governance blocks workspace prefix bypass paths');
}

function testWorkspaceBoundarySymlinkEscape() {
  if (process.platform === 'win32') {
    console.log('SKIP tool governance symlink escape on win32');
    return;
  }

  const repoRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'tool-governance-link-'));
  const workspaceRoot = path.join(repoRoot, 'workspace');
  const outsideRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'tool-governance-outside-'));
  fs.mkdirSync(workspaceRoot, { recursive: true });
  fs.symlinkSync(outsideRoot, path.join(workspaceRoot, 'escape'));

  const out = decide(
    { action: 'fs_write_outside_repo', targetPath: path.join(workspaceRoot, 'escape', 'loot.txt') },
    { trustLevel: 'untrusted' },
    { repoRoot }
  );
  assert.strictEqual(out.decision, 'ask');
  console.log('PASS tool governance blocks symlink escapes outside workspace');
}

function main() {
  testAllowlistAction();
  testAskThresholds();
  testDenylistAction();
  testWorkspaceBoundaryPrefixAndTraversalChecks();
  testWorkspaceBoundarySymlinkEscape();
}

main();
