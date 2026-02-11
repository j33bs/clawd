'use strict';

const assert = require('node:assert/strict');
const { BudgetCircuitBreaker, STATES } = require('../core/system2/budget_circuit_breaker');

function run(name, fn) {
  try {
    fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}: ${error.message}`);
    process.exitCode = 1;
  }
}

run('starts in closed state with zero usage', () => {
  const breaker = new BudgetCircuitBreaker({ tokenCap: 1000, callCap: 10 });
  const alloc = breaker.getAllocation();
  assert.equal(alloc.state, STATES.CLOSED);
  assert.equal(alloc.remaining, 1000);
  assert.equal(alloc.tokens_used, 0);
  assert.equal(alloc.calls_made, 0);
});

run('records usage and decrements remaining', () => {
  const breaker = new BudgetCircuitBreaker({ tokenCap: 1000, callCap: 10 });
  const result = breaker.recordUsage({ inputTokens: 100, outputTokens: 50 });
  assert.equal(result.ok, true);
  assert.equal(result.tokensUsed, 150);
  assert.equal(result.remaining, 850);
  assert.equal(result.callsMade, 1);
});

run('trips on token cap exceeded', () => {
  const events = [];
  const breaker = new BudgetCircuitBreaker({
    tokenCap: 200,
    callCap: 100,
    onEvent: (e) => events.push(e)
  });
  breaker.recordUsage({ inputTokens: 100, outputTokens: 50 });
  const result = breaker.recordUsage({ inputTokens: 30, outputTokens: 30 });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'token_cap_exceeded');
  assert.equal(breaker.state, STATES.OPEN);
  assert.equal(events.length, 1);
  assert.equal(events[0].event_type, 'budget_exhausted');
});

run('trips on call cap exceeded', () => {
  const breaker = new BudgetCircuitBreaker({ tokenCap: 100000, callCap: 2 });
  breaker.recordUsage({ inputTokens: 10 });
  const result = breaker.recordUsage({ inputTokens: 10 });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'call_cap_exceeded');
});

run('rejects usage when open', () => {
  const breaker = new BudgetCircuitBreaker({ tokenCap: 100, callCap: 100 });
  breaker.recordUsage({ inputTokens: 100 });
  const result = breaker.recordUsage({ inputTokens: 10 });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'budget_exhausted');
});

run('canProceed returns false when open', () => {
  const breaker = new BudgetCircuitBreaker({ tokenCap: 100, callCap: 100 });
  assert.equal(breaker.canProceed(50), true);
  breaker.recordUsage({ inputTokens: 100 });
  assert.equal(breaker.canProceed(0), false);
});

run('canProceed returns false when estimate exceeds remaining', () => {
  const breaker = new BudgetCircuitBreaker({ tokenCap: 100, callCap: 100 });
  breaker.recordUsage({ inputTokens: 80 });
  assert.equal(breaker.canProceed(30), false);
  assert.equal(breaker.canProceed(10), true);
});

run('reset restores closed state', () => {
  const events = [];
  const breaker = new BudgetCircuitBreaker({
    tokenCap: 100,
    callCap: 100,
    onEvent: (e) => events.push(e)
  });
  breaker.recordUsage({ inputTokens: 100 });
  assert.equal(breaker.state, STATES.OPEN);

  const alloc = breaker.reset();
  assert.equal(alloc.state, STATES.CLOSED);
  assert.equal(alloc.remaining, 100);
  assert.equal(alloc.tokens_used, 0);
  assert.equal(alloc.calls_made, 0);

  // Should have emitted budget_exhausted + budget_reset
  assert.equal(events.length, 2);
  assert.equal(events[1].event_type, 'budget_reset');
});

run('reset with new caps', () => {
  const breaker = new BudgetCircuitBreaker({ tokenCap: 100, callCap: 10 });
  breaker.recordUsage({ inputTokens: 100 });
  const alloc = breaker.reset({ tokenCap: 5000, callCap: 50 });
  assert.equal(alloc.cap, 5000);
  assert.equal(alloc.call_cap, 50);
  assert.equal(alloc.remaining, 5000);
});

console.log('budget_circuit_breaker tests complete');
