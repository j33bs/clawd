const assert = require('assert');

const { callModel } = require('../core/model_call');
const { createModelRuntime } = require('../core/model_runtime');
const { BACKENDS, TASK_CLASSES } = require('../core/model_constants');
const ModelRouter = require('../core/router');

function makeProvider(overrides = {}) {
  return {
    health: overrides.health || (async () => ({ ok: true })),
    call: overrides.call || (async () => ({ text: 'ok', raw: {}, usage: null }))
  };
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

async function testLocalFallbackAllowedIntent() {
  let localCalls = 0;
  const router = new ModelRouter({
    localFallbackEnabled: true,
    localBackends: [BACKENDS.LOCAL_OLLAMA]
  });

  global.__OPENCLAW_MODEL_RUNTIME = createModelRuntime({
    persistLogs: false,
    router,
    providers: {
      [BACKENDS.OATH_CLAUDE]: makeProvider({
        call: async () => {
          const error = new Error('rate_limit');
          error.status = 429;
          error.code = 'rate_limit';
          throw error;
        }
      }),
      [BACKENDS.ANTHROPIC_CLAUDE_API]: makeProvider({
        call: async () => {
          const error = new Error('rate_limit');
          error.status = 429;
          error.code = 'rate_limit';
          throw error;
        }
      }),
      [BACKENDS.LOCAL_OLLAMA]: makeProvider({
        call: async () => {
          localCalls += 1;
          return { text: 'local-ok', raw: {}, usage: null };
        }
      })
    }
  });

  const result = await callModel({
    taskId: 'test_local_allowed',
    messages: [{ role: 'user', content: 'summarize logs' }],
    taskClass: TASK_CLASSES.BASIC,
    metadata: { intent: 'summarize' }
  });

  assert.strictEqual(result.backend, BACKENDS.LOCAL_OLLAMA);
  assert.strictEqual(localCalls, 1, 'expected local provider to be called');
}

async function testLocalFallbackBlockedIntent() {
  let localCalls = 0;
  const router = new ModelRouter({
    localFallbackEnabled: true,
    localBackends: [BACKENDS.LOCAL_OLLAMA]
  });

  global.__OPENCLAW_MODEL_RUNTIME = createModelRuntime({
    persistLogs: false,
    router,
    providers: {
      [BACKENDS.OATH_CLAUDE]: makeProvider({
        call: async () => {
          const error = new Error('rate_limit');
          error.status = 429;
          error.code = 'rate_limit';
          throw error;
        }
      }),
      [BACKENDS.ANTHROPIC_CLAUDE_API]: makeProvider({
        call: async () => {
          const error = new Error('rate_limit');
          error.status = 429;
          error.code = 'rate_limit';
          throw error;
        }
      }),
      [BACKENDS.LOCAL_OLLAMA]: makeProvider({
        call: async () => {
          localCalls += 1;
          return { text: 'local-ok', raw: {}, usage: null };
        }
      })
    }
  });

  let didThrow = false;
  try {
    await callModel({
      taskId: 'test_local_blocked',
      messages: [{ role: 'user', content: 'research deep synthesis' }],
      taskClass: TASK_CLASSES.NON_BASIC,
      metadata: { intent: 'research' }
    });
  } catch (error) {
    didThrow = true;
    assert.strictEqual(error.code, 'LOCAL_FALLBACK_DISALLOWED');
  }

  if (!didThrow) {
    throw new Error('expected local fallback to be blocked');
  }
  assert.strictEqual(localCalls, 0, 'expected local provider not to be called');
}

async function main() {
  await runTest('local fallback allowed for summarize intent', testLocalFallbackAllowedIntent);
  await runTest('local fallback blocked for research intent', testLocalFallbackBlockedIntent);
}

main().catch(() => {
  process.exit(1);
});
