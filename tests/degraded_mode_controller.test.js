'use strict';

const assert = require('node:assert/strict');
const { DegradedModeController, MODES } = require('../core/system2/degraded_mode_controller');

function run(name, fn) {
  try {
    fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}: ${error.message}`);
    process.exitCode = 1;
  }
}

run('starts in normal mode', () => {
  const ctrl = new DegradedModeController();
  assert.equal(ctrl.mode, MODES.NORMAL);
  const flags = ctrl.getDegradeFlags();
  assert.equal(flags.tools_disabled, false);
  assert.equal(flags.local_only, false);
  assert.equal(flags.read_only_memory, false);
  assert.equal(flags.deny_reason, null);
});

run('transitions to degraded mode', () => {
  const events = [];
  const ctrl = new DegradedModeController({ onEvent: (e) => events.push(e) });
  const state = ctrl.transitionTo(MODES.DEGRADED, 'test_reason');
  assert.equal(state.mode, MODES.DEGRADED);
  assert.equal(state.reason, 'test_reason');
  assert.equal(events.length, 1);
  assert.equal(events[0].event_type, 'degraded_mode_entered');
  assert.equal(events[0].new_mode, MODES.DEGRADED);
});

run('degraded mode flags are correct', () => {
  const ctrl = new DegradedModeController();
  ctrl.transitionTo(MODES.DEGRADED, 'budget_exhausted');
  const flags = ctrl.getDegradeFlags();
  assert.equal(flags.tools_disabled, true);
  assert.equal(flags.local_only, true);
  assert.equal(flags.read_only_memory, true);
  assert.equal(flags.deny_reason, 'budget_exhausted');
});

run('recovery mode flags are correct', () => {
  const ctrl = new DegradedModeController();
  ctrl.transitionTo(MODES.RECOVERY, 'system1_unavailable');
  const flags = ctrl.getDegradeFlags();
  assert.equal(flags.tools_disabled, false);
  assert.equal(flags.local_only, true);
  assert.equal(flags.read_only_memory, false);
  assert.equal(flags.deny_reason, null);
});

run('burst mode flags are correct', () => {
  const ctrl = new DegradedModeController();
  ctrl.transitionTo(MODES.BURST, 'system1_saturated');
  const flags = ctrl.getDegradeFlags();
  assert.equal(flags.tools_disabled, false);
  assert.equal(flags.local_only, false);
});

run('same mode transition is a no-op', () => {
  const events = [];
  const ctrl = new DegradedModeController({ onEvent: (e) => events.push(e) });
  ctrl.transitionTo(MODES.DEGRADED, 'first');
  const eventCount = events.length;
  ctrl.transitionTo(MODES.DEGRADED, 'duplicate');
  assert.equal(events.length, eventCount); // no new event
});

run('invalid mode throws', () => {
  const ctrl = new DegradedModeController();
  assert.throws(() => ctrl.transitionTo('invalid_mode'), /Invalid mode/);
});

run('evaluate transitions to recovery when system1 down', () => {
  const ctrl = new DegradedModeController();
  ctrl.evaluate({ system1: { state: 'down' } });
  assert.equal(ctrl.mode, MODES.RECOVERY);
});

run('evaluate transitions to burst when system1 saturated', () => {
  const ctrl = new DegradedModeController();
  ctrl.evaluate({ system1: { state: 'saturated' } });
  assert.equal(ctrl.mode, MODES.BURST);
});

run('evaluate transitions to degraded when budget exhausted', () => {
  const ctrl = new DegradedModeController();
  ctrl.evaluate({ system1: { state: 'up' }, budget_exhausted: true });
  assert.equal(ctrl.mode, MODES.DEGRADED);
});

run('evaluate transitions to degraded when local inference unavailable', () => {
  const ctrl = new DegradedModeController();
  ctrl.evaluate({
    system1: { state: 'up' },
    system2: { inference_ok: false }
  });
  assert.equal(ctrl.mode, MODES.DEGRADED);
});

run('evaluate transitions back to normal when health restored', () => {
  const ctrl = new DegradedModeController();
  ctrl.transitionTo(MODES.DEGRADED, 'test');
  ctrl.evaluate({
    system1: { state: 'up' },
    system2: { inference_ok: true },
    budget_exhausted: false
  });
  assert.equal(ctrl.mode, MODES.NORMAL);
});

run('history is maintained', () => {
  const ctrl = new DegradedModeController();
  ctrl.transitionTo(MODES.DEGRADED, 'reason1');
  ctrl.transitionTo(MODES.RECOVERY, 'reason2');
  ctrl.transitionTo(MODES.NORMAL, 'reason3');
  const state = ctrl.getState();
  assert.equal(state.history_length, 3);
});

run('history is bounded by maxHistory', () => {
  const ctrl = new DegradedModeController({ maxHistory: 2 });
  ctrl.transitionTo(MODES.DEGRADED, 'a');
  ctrl.transitionTo(MODES.RECOVERY, 'b');
  ctrl.transitionTo(MODES.NORMAL, 'c');
  assert.equal(ctrl.history.length, 2);
});

console.log('degraded_mode_controller tests complete');
