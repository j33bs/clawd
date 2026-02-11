'use strict';

const assert = require('node:assert');

const { evaluateRoutingDecision } = require('../core/system2/routing_policy_contract');
const { BACKENDS } = require('../core/model_constants');

function run(name, fn) {
  try {
    fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    console.error(error.message);
    process.exit(1);
  }
}

run('routing policy is deterministic for same input', () => {
  const input = {
    request_type: 'coding',
    privacy_level: 'external_ok',
    urgency: 'interactive',
    provenance: 'first_party',
    tool_needs: ['read_file'],
    budget: {
      remaining: 3000,
      cap: 8000
    },
    system_health: {
      system1: { state: 'up' },
      system2: { mode: 'normal' }
    }
  };

  const first = evaluateRoutingDecision(input);
  const second = evaluateRoutingDecision(input);
  assert.deepStrictEqual(first, second);
});

run('routing policy forces local_only for privacy local_only', () => {
  const decision = evaluateRoutingDecision({
    request_type: 'general',
    privacy_level: 'local_only',
    budget: { remaining: 3000, cap: 8000 }
  });

  assert.strictEqual(decision.degrade_flags.local_only, true);
  assert.strictEqual(decision.selected_model_route, BACKENDS.LOCAL_QWEN);
});

run('routing policy denies when budget is exhausted', () => {
  const decision = evaluateRoutingDecision({
    request_type: 'analysis',
    privacy_level: 'external_ok',
    budget: { remaining: 0, cap: 8000 }
  });

  assert.strictEqual(decision.degrade_flags.deny_reason, 'budget_exhausted');
  assert.strictEqual(decision.degrade_flags.tools_disabled, true);
});
