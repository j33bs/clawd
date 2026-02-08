const assert = require('assert');
const path = require('path');

const { callModel } = require('../core/model_call');
const { BACKENDS } = require('../core/model_constants');

const CONTROLLED_CONSTITUTION_UNAVAILABLE_MESSAGE =
  'Constitution unavailable; refusing to run to preserve governance integrity.';
const FIXTURE_DIR = path.join(__dirname, 'fixtures', 'constitution');

function createRuntime() {
  const calls = [];
  return {
    calls,
    runtime: {
      router: {
        buildRoutePlan() {
          return {
            taskClass: 'NON_BASIC',
            requiresClaude: false,
            allowNetwork: true,
            preferredBackend: BACKENDS.OATH_CLAUDE,
            candidates: [BACKENDS.OATH_CLAUDE]
          };
        },
        isLocalBackend() {
          return false;
        },
        networkUsedForBackend() {
          return true;
        },
        cooldownKeyForBackend() {
          return null;
        }
      },
      cooldownManager: {
        clearExpired() {
          return [];
        }
      },
      logger: {
        async logFallbackEvent() {},
        async logNotification() {}
      },
      providers: {
        [BACKENDS.OATH_CLAUDE]: {
          model: 'oath-test-model',
          async health() {
            return { ok: true };
          },
          async call(payload) {
            calls.push(payload);
            return { text: 'ok', raw: { provider: 'oath' }, usage: null };
          }
        }
      }
    }
  };
}

function withEnv(overrides, fn) {
  const previous = {};
  for (const [key, value] of Object.entries(overrides)) {
    previous[key] = process.env[key];
    if (value == null) {
      delete process.env[key];
    } else {
      process.env[key] = String(value);
    }
  }

  return Promise.resolve()
    .then(fn)
    .finally(() => {
      for (const [key, value] of Object.entries(previous)) {
        if (value == null) {
          delete process.env[key];
        } else {
          process.env[key] = value;
        }
      }
    });
}

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

async function testGateOffLeavesPromptUnchanged() {
  const { runtime, calls } = createRuntime();
  global.__OPENCLAW_MODEL_RUNTIME = runtime;

  try {
    await withEnv(
      {
        OPENCLAW_CONSTITUTION_ENFORCE: null,
        OPENCLAW_CONSTITUTION_SOURCE_PATH: null,
        OPENCLAW_CONSTITUTION_SUPPORTING_PATHS: null,
        OPENCLAW_CONSTITUTION_MAX_CHARS: null
      },
      async () => {
        await callModel({
          taskId: 'constitution_gate_off',
          taskClass: 'NON_BASIC',
          messages: [
            { role: 'system', content: 'base-system' },
            { role: 'user', content: 'hello' }
          ],
          metadata: {}
        });
      }
    );
  } finally {
    delete global.__OPENCLAW_MODEL_RUNTIME;
  }

  assert.strictEqual(calls.length, 1, 'provider should be called when gate is off');
  const combinedSystem = calls[0].messages
    .filter((message) => String(message.role || '').toLowerCase() === 'system')
    .map((message) => String(message.content || ''))
    .join('\n');
  assert.ok(combinedSystem.includes('base-system'));
  assert.ok(!combinedSystem.includes('[CONSTITUTION_BEGIN'));
}

async function testGateOnInjectsConstitutionBlock() {
  const { runtime, calls } = createRuntime();
  global.__OPENCLAW_MODEL_RUNTIME = runtime;

  const sourcePath = path.join(FIXTURE_DIR, 'constitution_source.md');
  const supporting = [
    path.join(FIXTURE_DIR, 'supporting_governance.md'),
    path.join(FIXTURE_DIR, 'supporting_agents.md')
  ].join(path.delimiter);

  try {
    await withEnv(
      {
        OPENCLAW_CONSTITUTION_ENFORCE: '1',
        OPENCLAW_CONSTITUTION_SOURCE_PATH: sourcePath,
        OPENCLAW_CONSTITUTION_SUPPORTING_PATHS: supporting,
        OPENCLAW_CONSTITUTION_MAX_CHARS: '300'
      },
      async () => {
        await callModel({
          taskId: 'constitution_gate_on',
          taskClass: 'NON_BASIC',
          messages: [
            { role: 'system', content: 'base-system' },
            { role: 'user', content: 'hello' }
          ],
          metadata: {}
        });
      }
    );
  } finally {
    delete global.__OPENCLAW_MODEL_RUNTIME;
  }

  assert.strictEqual(calls.length, 1, 'provider should be called when constitution is available');
  const combinedSystem = calls[0].messages
    .filter((message) => String(message.role || '').toLowerCase() === 'system')
    .map((message) => String(message.content || ''))
    .join('\n');

  assert.ok(combinedSystem.includes('[CONSTITUTION_BEGIN sha256='));
  assert.ok(combinedSystem.includes('[CONSTITUTION_END]'));
  assert.ok(combinedSystem.includes('[TRUNCATED]'));
  assert.ok(combinedSystem.length <= 12000, 'system prompt must respect cap');
}

async function testGateOnFailsClosedWhenConstitutionUnavailable() {
  const { runtime, calls } = createRuntime();
  global.__OPENCLAW_MODEL_RUNTIME = runtime;

  let result;
  try {
    await withEnv(
      {
        OPENCLAW_CONSTITUTION_ENFORCE: '1',
        OPENCLAW_CONSTITUTION_SOURCE_PATH: path.join(FIXTURE_DIR, 'missing_source.md'),
        OPENCLAW_CONSTITUTION_SUPPORTING_PATHS: null,
        OPENCLAW_CONSTITUTION_MAX_CHARS: '300'
      },
      async () => {
        result = await callModel({
          taskId: 'constitution_gate_fail',
          taskClass: 'NON_BASIC',
          messages: [{ role: 'user', content: 'hello' }],
          metadata: {}
        });
      }
    );
  } finally {
    delete global.__OPENCLAW_MODEL_RUNTIME;
  }

  assert.strictEqual(calls.length, 0, 'provider call must be blocked when constitution load fails');
  assert.ok(result, 'expected controlled result object');
  assert.strictEqual(result.response.text, CONTROLLED_CONSTITUTION_UNAVAILABLE_MESSAGE);
  assert.strictEqual(result.response.raw.reason, 'CONSTITUTION_UNAVAILABLE');
}

async function main() {
  await runTest('gate off leaves prompt unchanged', testGateOffLeavesPromptUnchanged);
  await runTest('gate on injects constitution block', testGateOnInjectsConstitutionBlock);
  await runTest('gate on fails closed when constitution missing', testGateOnFailsClosedWhenConstitutionUnavailable);
}

main().catch(() => process.exit(1));
