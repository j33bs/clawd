'use strict';

const assert = require('node:assert/strict');
const { BudgetCircuitBreaker, STATES, DEFAULT_ACTION_CLASS_CAPS, LOOP_WINDOW, LOOP_MIN_REPEAT } = require('../core/system2/budget_circuit_breaker');

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

// ── Phase 4: Action-class caps ────────────────────────────────────────────

run('recordAction: Class A is always permitted (no cap)', () => {
  const breaker = new BudgetCircuitBreaker({ tokenCap: 100000, callCap: 1000 });
  for (let i = 0; i < 20; i++) {
    const r = breaker.recordAction('A', `tool_${i}`, `args_${i}`);
    assert.equal(r.ok, true, `Class A action ${i} must be ok`);
  }
  assert.equal(breaker.actionClassCounts.A, 20);
});

run('recordAction: Class D trips at default cap (5)', () => {
  const breaker = new BudgetCircuitBreaker({
    tokenCap: 100000,
    callCap: 1000,
    actionClassCaps: { D: 5 }
  });
  for (let i = 0; i < 4; i++) {
    const r = breaker.recordAction('D', 'delete_file', `file_${i}`);
    assert.equal(r.ok, true, `Class D action ${i} must be ok`);
  }
  // 5th call hits the cap.
  const tripped = breaker.recordAction('D', 'delete_file', 'final');
  assert.equal(tripped.ok, false);
  assert.match(tripped.reason, /action_class_cap_exceeded:D/);
  assert.equal(breaker.state, STATES.OPEN);
});

run('recordAction: custom actionClassCaps respected', () => {
  const breaker = new BudgetCircuitBreaker({
    tokenCap: 100000,
    callCap: 1000,
    actionClassCaps: { D: 2, C: 3 }
  });
  breaker.recordAction('D', 'tool', 'a');
  const r2 = breaker.recordAction('D', 'tool', 'b');
  assert.equal(r2.ok, false, 'should trip at cap=2 on 2nd D action');
  assert.match(r2.reason, /action_class_cap_exceeded:D/);
});

run('recordAction: Class C cap enforced', () => {
  const breaker = new BudgetCircuitBreaker({
    tokenCap: 100000,
    callCap: 1000,
    actionClassCaps: { C: 3 }
  });
  breaker.recordAction('C', 'restart_service', 'nginx');
  breaker.recordAction('C', 'restart_service', 'redis');
  const r3 = breaker.recordAction('C', 'reload_config', 'app');
  assert.equal(r3.ok, false);
  assert.match(r3.reason, /action_class_cap_exceeded:C/);
});

run('recordAction: unknown class returns error', () => {
  const breaker = new BudgetCircuitBreaker({ tokenCap: 100000, callCap: 1000 });
  const r = breaker.recordAction('Z', 'unknown_tool', '');
  assert.equal(r.ok, false);
  assert.match(r.reason, /unknown_action_class:Z/);
});

run('recordAction: rejects when breaker already open', () => {
  const breaker = new BudgetCircuitBreaker({ tokenCap: 10, callCap: 1000 });
  breaker.recordUsage({ inputTokens: 10 }); // trips on token cap
  const r = breaker.recordAction('A', 'read_file', '');
  assert.equal(r.ok, false);
  assert.equal(r.reason, 'budget_exhausted');
});

run('reset clears actionClassCounts and recentTools', () => {
  const breaker = new BudgetCircuitBreaker({
    tokenCap: 100000,
    callCap: 1000,
    actionClassCaps: { D: 10 }
  });
  breaker.recordAction('D', 'tool', 'a');
  breaker.recordAction('B', 'tool2', 'b');
  assert.equal(breaker.actionClassCounts.D, 1);
  assert.equal(breaker.actionClassCounts.B, 1);

  breaker.reset();
  assert.equal(breaker.actionClassCounts.D, 0);
  assert.equal(breaker.actionClassCounts.B, 0);
  assert.equal(breaker.recentTools.length, 0);
});

// ── Phase 4: Loop detection ───────────────────────────────────────────────

run('isLooping: returns false with < LOOP_MIN_REPEAT repeats', () => {
  const breaker = new BudgetCircuitBreaker({ tokenCap: 100000, callCap: 1000 });
  // Push LOOP_MIN_REPEAT - 1 identical calls.
  for (let i = 0; i < LOOP_MIN_REPEAT - 1; i++) {
    breaker.recordAction('A', 'same_tool', 'same_args');
  }
  assert.equal(breaker.isLooping(), false);
});

run('isLooping: trips breaker at LOOP_MIN_REPEAT identical calls', () => {
  const breaker = new BudgetCircuitBreaker({ tokenCap: 100000, callCap: 1000 });
  // First LOOP_MIN_REPEAT - 1 calls must succeed.
  for (let i = 0; i < LOOP_MIN_REPEAT - 1; i++) {
    const r = breaker.recordAction('A', 'looping_tool', 'same_args');
    assert.equal(r.ok, true, `call ${i} must be ok`);
  }
  // LOOP_MIN_REPEAT-th call should trip.
  const r = breaker.recordAction('A', 'looping_tool', 'same_args');
  assert.equal(r.ok, false);
  assert.equal(r.reason, 'autonomous_loop_detected');
  assert.equal(breaker.state, STATES.OPEN);
});

run('loop window rolls over: old repeats fall out', () => {
  const breaker = new BudgetCircuitBreaker({ tokenCap: 100000, callCap: 1000, actionClassCaps: {} });
  // Fill window with LOOP_WINDOW - LOOP_MIN_REPEAT + 1 distinct tools.
  const distinctCount = LOOP_WINDOW - LOOP_MIN_REPEAT + 1;
  for (let i = 0; i < distinctCount; i++) {
    breaker.recordAction('A', `distinct_${i}`, '');
  }
  // Now add LOOP_MIN_REPEAT - 1 occurrences of the repeated tool.
  for (let i = 0; i < LOOP_MIN_REPEAT - 1; i++) {
    const r = breaker.recordAction('A', 'repeated_tool', 'args');
    assert.equal(r.ok, true);
  }
  // The window now has LOOP_WINDOW items; the first occurrence of 'repeated_tool'
  // would need to be within the window for a loop.  Because we added enough distinct
  // calls first, the earliest repeated_tool calls should still be in-window.
  // One more 'repeated_tool' call should trip.
  const r = breaker.recordAction('A', 'repeated_tool', 'args');
  assert.equal(r.ok, false);
  assert.equal(r.reason, 'autonomous_loop_detected');
});

run('getAllocation includes action_class_counts and action_class_caps', () => {
  const breaker = new BudgetCircuitBreaker({
    tokenCap: 100000,
    callCap: 1000,
    actionClassCaps: { D: 5, C: 10 }
  });
  breaker.recordAction('B', 'write_file', 'foo');
  breaker.recordAction('E', 'api_call', 'bar');
  const alloc = breaker.getAllocation();
  assert.deepEqual(alloc.action_class_counts, { A: 0, B: 1, C: 0, D: 0, E: 1 });
  assert.equal(alloc.action_class_caps.D, 5);
  assert.equal(alloc.action_class_caps.C, 10);
});

run('DEFAULT_ACTION_CLASS_CAPS exported correctly', () => {
  assert.equal(DEFAULT_ACTION_CLASS_CAPS.D, 5);
  assert.equal(DEFAULT_ACTION_CLASS_CAPS.C, 10);
});

console.log('budget_circuit_breaker tests complete');
