const assert = require('assert');

const { enforceBudget } = require('../core/chain/chain_budget');

async function runTest(name, fn) {
  try {
    await fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    console.error(`  ${error.message}`);
    throw error;
  }
}

async function testPinnedSurvives() {
  const state = {
    working: {
      pinned: {
        constitutionNote: 'CONST',
        truncationNote: 'NOTE',
        userIntent: 'INTENT',
        invariants: 'INVAR'
      },
      rollingSummary: 'x'.repeat(2000),
      scratch: { perTask: { a: 'b'.repeat(5000) } }
    },
    outputs: { artifacts: [{ text: 'c'.repeat(2000) }] }
  };

  const result = enforceBudget(state, 200);
  assert.strictEqual(result.ok, false);
  assert.ok(result.state.working.pinned.userIntent.includes('INTENT'));
  assert.ok(result.state.working.pinned.truncationNote.includes('NOTE'));
}

async function testScratchDroppedBeforeRolling() {
  const state = {
    working: {
      pinned: { truncationNote: 'NOTE' },
      rollingSummary: 'summary',
      scratch: { perTask: { a: 'x'.repeat(5000) } }
    }
  };

  const result = enforceBudget(state, 200);
  assert.deepStrictEqual(result.state.working.scratch.perTask, {});
}

async function testDeterministic() {
  const state = {
    working: {
      pinned: { truncationNote: 'NOTE' },
      rollingSummary: 'summary',
      scratch: { perTask: { a: 'x'.repeat(5000) } }
    }
  };

  const a = enforceBudget(state, 200);
  const b = enforceBudget(state, 200);
  assert.deepStrictEqual(a.state, b.state);
}

async function main() {
  await runTest('pinned content survives aggressive truncation', testPinnedSurvives);
  await runTest('scratch dropped before rollingSummary', testScratchDroppedBeforeRolling);
  await runTest('budgeting is deterministic', testDeterministic);
}

main().catch(() => {
  process.exit(1);
});
