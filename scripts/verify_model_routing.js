#!/usr/bin/env node

const { callModel } = require('../core/model_call');
const { createModelRuntime } = require('../core/model_runtime');
const { BACKENDS, TASK_CLASSES } = require('../core/model_constants');

function assertEqual(actual, expected, label) {
  if (actual !== expected) {
    throw new Error(`${label} expected ${expected}, got ${actual}`);
  }
}

function hasRouteSelect(events, toBackend) {
  return events.some(
    (event) => event && event.event_type === 'ROUTE_SELECT' && event.to_backend === toBackend
  );
}

function hasNotification(events) {
  return events.some((event) => event && event.type === 'routing_notice');
}

async function runCase(name, fn) {
  try {
    await fn();
    console.log(`PASS ${name}`);
    return true;
  } catch (error) {
    console.error(`FAIL ${name}`);
    console.error(`  ${error.message}`);
    return false;
  }
}

function buildRuntime(options = {}) {
  return createModelRuntime({
    persistLogs: false,
    oathInvokeFn: options.oathInvokeFn,
    qwenInvokeFn: options.qwenInvokeFn
  });
}

async function main() {
  let passCount = 0;
  let failCount = 0;

  const basicCase = await runCase('BASIC routes to LOCAL_QWEN by default', async () => {
    global.__OPENCLAW_MODEL_RUNTIME = buildRuntime({
      oathInvokeFn: async () => ({ text: 'oath', raw: {}, usage: null }),
      qwenInvokeFn: async () => ({ text: 'qwen', raw: {}, usage: null })
    });

    const result = await callModel({
      taskId: 'verify_basic',
      messages: [{ role: 'user', content: 'list files in project' }],
      taskClass: TASK_CLASSES.BASIC,
      metadata: {}
    });

    assertEqual(result.backend, BACKENDS.LOCAL_QWEN, 'backend');
  });

  if (basicCase) {
    passCount += 1;
  } else {
    failCount += 1;
  }

  const healthyCase = await runCase('NON_BASIC uses OATH when healthy', async () => {
    global.__OPENCLAW_MODEL_RUNTIME = buildRuntime({
      oathInvokeFn: async () => ({ text: 'oath-ok', raw: {}, usage: { totalTokens: 5 } }),
      qwenInvokeFn: async () => ({ text: 'qwen-ok', raw: {}, usage: { totalTokens: 5 } })
    });

    const result = await callModel({
      taskId: 'verify_nonbasic_healthy',
      messages: [{ role: 'user', content: 'propose architecture changes' }],
      taskClass: TASK_CLASSES.NON_BASIC,
      metadata: {}
    });

    assertEqual(result.backend, BACKENDS.OATH_CLAUDE, 'backend');
  });

  if (healthyCase) {
    passCount += 1;
  } else {
    failCount += 1;
  }

  const oathFailureCase = await runCase('OATH AUTH failure falls back to ANTHROPIC', async () => {
    global.__OPENCLAW_MODEL_RUNTIME = buildRuntime({
      oathInvokeFn: async () => {
        const error = new Error('authentication_error');
        error.status = 401;
        error.code = 'authentication_error';
        throw error;
      },
      qwenInvokeFn: async () => ({ text: 'qwen-ok', raw: {}, usage: { totalTokens: 5 } })
    });

    const result = await callModel({
      taskId: 'verify_oath_auth',
      messages: [{ role: 'user', content: 'complex debugging with invariants' }],
      taskClass: TASK_CLASSES.NON_BASIC,
      metadata: {
        anthropicApiKey: 'test-key',
        simulation: {
          anthropicSuccess: true
        }
      }
    });

    assertEqual(result.backend, BACKENDS.ANTHROPIC_CLAUDE_API, 'backend');
    if (!hasRouteSelect(result.events, BACKENDS.ANTHROPIC_CLAUDE_API)) {
      throw new Error('expected ROUTE_SELECT event for Anthropic fallback');
    }
  });

  if (oathFailureCase) {
    passCount += 1;
  } else {
    failCount += 1;
  }

  const oathRateLimitCase = await runCase(
    'OATH RATE_LIMIT failure falls back to ANTHROPIC',
    async () => {
      global.__OPENCLAW_MODEL_RUNTIME = buildRuntime({
        oathInvokeFn: async () => {
          const error = new Error('rate_limit');
          error.status = 429;
          error.code = 'rate_limit';
          throw error;
        },
        qwenInvokeFn: async () => ({ text: 'qwen-ok', raw: {}, usage: { totalTokens: 5 } })
      });

      const result = await callModel({
        taskId: 'verify_oath_rate_limit',
        messages: [{ role: 'user', content: 'deep reasoning architecture task' }],
        taskClass: TASK_CLASSES.NON_BASIC,
        metadata: {
          anthropicApiKey: 'test-key',
          simulation: {
            anthropicSuccess: true
          }
        }
      });

      assertEqual(result.backend, BACKENDS.ANTHROPIC_CLAUDE_API, 'backend');
    }
  );

  if (oathRateLimitCase) {
    passCount += 1;
  } else {
    failCount += 1;
  }

  const anthropicFailureCase = await runCase(
    'Anthropic unavailable falls back to LOCAL_QWEN with notification',
    async () => {
      delete process.env.ANTHROPIC_API_KEY;
      global.__OPENCLAW_MODEL_RUNTIME = buildRuntime({
        oathInvokeFn: async () => {
          const error = new Error('rate_limit');
          error.status = 429;
          error.code = 'rate_limit';
          throw error;
        },
        qwenInvokeFn: async () => ({ text: 'qwen-ok', raw: {}, usage: { totalTokens: 5 } })
      });

      const result = await callModel({
        taskId: 'verify_anthropic_missing_key',
        messages: [{ role: 'user', content: 'multi-file invariant refactor' }],
        taskClass: TASK_CLASSES.NON_BASIC,
        metadata: {}
      });

      assertEqual(result.backend, BACKENDS.LOCAL_QWEN, 'backend');
      if (!hasNotification(result.events)) {
        throw new Error('expected routing_notice notification for LOCAL_QWEN fallback');
      }
    }
  );

  if (anthropicFailureCase) {
    passCount += 1;
  } else {
    failCount += 1;
  }

  console.log(`\nSummary: ${passCount} passed, ${failCount} failed`);

  if (failCount > 0) {
    process.exit(1);
  }
}

main().catch((error) => {
  console.error('FAIL verify_model_routing');
  console.error(`  ${error.message}`);
  process.exit(1);
});
