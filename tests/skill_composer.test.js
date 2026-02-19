'use strict';

const assert = require('node:assert');
const { composeWorkflow } = require('../core/system2/skill_composer');

function testFlagDisabledByDefault() {
  const out = composeWorkflow(
    { goal: 'test', toolCalls: [{ tool: 'exec', action: 'spawn_child_process' }] },
    { env: {} }
  );
  assert.strictEqual(out.enabled, false);
  assert.strictEqual(out.steps.length, 0);
  console.log('PASS skill composer is disabled by default');
}

function testGovernanceConstrainedSteps() {
  const out = composeWorkflow(
    {
      goal: 'prepare summary',
      toolCalls: [
        { tool: 'status', action: 'read_status' },
        { tool: 'exec', action: 'spawn_child_process' },
        { tool: 'net', action: 'gateway_rpc_broad' }
      ],
      context: { trustLevel: 'untrusted' }
    },
    {
      env: { OPENCLAW_ENABLE_SKILL_COMPOSER: '1' },
      repoRoot: '/tmp/repo'
    }
  );

  assert.strictEqual(out.enabled, true);
  assert.strictEqual(out.steps[0].decision, 'allow');
  assert.strictEqual(out.steps[1].decision, 'ask');
  assert.strictEqual(out.steps[1].executable, false);
  assert.strictEqual(out.steps[2].decision, 'ask');
  console.log('PASS skill composer respects tool governance decisions');
}

function main() {
  testFlagDisabledByDefault();
  testGovernanceConstrainedSteps();
}

main();
