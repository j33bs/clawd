'use strict';

const assert = require('node:assert');
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

function main() {
  testAllowlistAction();
  testAskThresholds();
  testDenylistAction();
}

main();
