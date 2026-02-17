'use strict';

const assert = require('node:assert');
const {
  requireApproval,
  ApprovalRequiredError,
  ToolDeniedError
} = require('../core/system2/security/ask_first');

function testExecNeedsApproval() {
  assert.throws(
    () => requireApproval('spawn_child_process', { trustLevel: 'trusted' }, { env: {} }),
    (err) => err instanceof ApprovalRequiredError
  );
  console.log('PASS ask_first enforces approval for exec');
}

function testOperatorApprovalTokenAllowsAskDecision() {
  const result = requireApproval(
    'gateway_rpc_broad',
    { trustLevel: 'untrusted' },
    { env: { OPENCLAW_OPERATOR_APPROVED: '1' } }
  );
  assert.strictEqual(result.allowed, true);
  console.log('PASS ask_first allows ask-decision action with operator approval');
}

function testDenyDecisionThrows() {
  assert.throws(
    () => requireApproval('policy_bypass_override', { trustLevel: 'trusted' }, { env: {} }),
    (err) => err instanceof ToolDeniedError
  );
  console.log('PASS ask_first surfaces deny decisions as ToolDeniedError');
}

function main() {
  testExecNeedsApproval();
  testOperatorApprovalTokenAllowsAskDecision();
  testDenyDecisionThrows();
}

main();
