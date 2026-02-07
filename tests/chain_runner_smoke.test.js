const assert = require('assert');
const fs = require('fs');

const { runChain } = require('../core/chain/chain_runner');

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

async function testChainRunnerSmoke() {
  const tracePath = 'logs/chain_runs/chain_trace_test.jsonl';
  const adapter = async () => ({ text: 'ok', usage: null });

  const state = await runChain('format this text', {
    modelAdapter: adapter,
    tracePath,
    maxTraceEntries: 10,
    tokenCeiling: 2000
  });

  assert.ok(state.outputs.finalText.includes('- '), 'expected final output');

  const content = await fs.promises.readFile(tracePath, 'utf8');
  const lines = content.split('\n').filter(Boolean);
  assert.ok(lines.length >= 3, 'expected trace lines');
}

async function main() {
  await runTest('chain runner smoke', testChainRunnerSmoke);
}

main().catch(() => {
  process.exit(1);
});
