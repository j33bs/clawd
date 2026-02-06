// guarded_fs_check.js
// Minimal regression check for guarded filesystem behavior.

const assert = require('assert');
const { readFileSync, resolveWorkspacePath, WORKSPACE_ROOT } = require('./guarded_fs');

function runChecks() {
  const deniedRead = readFileSync('/Users/example/Library/Autosave Information/deny.txt');
  assert.strictEqual(deniedRead, null, 'Denied path should return null');

  const agentsContent = readFileSync('AGENTS.md');
  assert.ok(agentsContent && agentsContent.includes('AGENTS.md'), 'Repo-relative read should succeed');

  const resolvedAgents = resolveWorkspacePath('AGENTS.md');
  assert.ok(resolvedAgents && resolvedAgents.startsWith(WORKSPACE_ROOT), 'Resolved path should be within workspace');

  console.log('guarded_fs_check: OK');
}

runChecks();
