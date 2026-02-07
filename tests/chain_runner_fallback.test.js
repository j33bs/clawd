const assert = require('assert');
const fs = require('fs');

const { runChain } = require('../core/chain/chain_runner');
const { BACKENDS } = require('../core/model_constants');

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

async function testFallbackTraceMarker() {
  const tracePath = 'logs/chain_runs/chain_trace_fallback.jsonl';
  const adapter = async () => ({ text: 'ok', backend: BACKENDS.OATH_CLAUDE });

  await runChain('write a design doc', {
    modelAdapter: adapter,
    tracePath,
    maxTraceEntries: 5,
    tokenCeiling: 2000
  });

  const content = await fs.promises.readFile(tracePath, 'utf8');
  const lines = content.split('\n').filter(Boolean);
  const parsed = lines.map((line) => JSON.parse(line));
  const execute = parsed.find((entry) => entry.step === 'EXECUTE');
  assert.ok(execute, 'expected execute trace');
  assert.strictEqual(execute.fallback_used, 'OATH_CLAUDE');
}

async function testNoFallbackMarkerWhenNotUsed() {
  const tracePath = 'logs/chain_runs/chain_trace_primary.jsonl';
  const adapter = async () => ({ text: 'ok', backend: BACKENDS.ANTHROPIC_CLAUDE_API });

  await runChain('write a design doc', {
    modelAdapter: adapter,
    tracePath,
    maxTraceEntries: 5,
    tokenCeiling: 2000
  });

  const content = await fs.promises.readFile(tracePath, 'utf8');
  const lines = content.split('\n').filter(Boolean);
  const parsed = lines.map((line) => JSON.parse(line));
  const execute = parsed.find((entry) => entry.step === 'EXECUTE');
  assert.ok(execute, 'expected execute trace');
  assert.strictEqual(execute.fallback_used, null);
}

async function main() {
  await runTest('trace marks OATH_CLAUDE fallback', testFallbackTraceMarker);
  await runTest('trace omits fallback marker for primary', testNoFallbackMarkerWhenNotUsed);
}

main().catch(() => {
  process.exit(1);
});
