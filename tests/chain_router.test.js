const assert = require('assert');

const { selectProfile } = require('../core/chain/chain_router');

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

async function testFormatRouting() {
  const profile = selectProfile({ intent: 'format' }, {});
  assert.strictEqual(profile, 'cheap_transform');
}

async function testRefactorRouting() {
  const profile = selectProfile({ intent: 'refactor' }, {});
  assert.strictEqual(profile, 'code_remote');
}

async function testDesignRouting() {
  const profile = selectProfile({ intent: 'design' }, {});
  assert.strictEqual(profile, 'reasoning_remote');
}

async function main() {
  await runTest('format routes to cheap_transform', testFormatRouting);
  await runTest('refactor routes to code_remote', testRefactorRouting);
  await runTest('design routes to reasoning_remote', testDesignRouting);
}

main().catch(() => {
  process.exit(1);
});
