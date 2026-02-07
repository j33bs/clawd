#!/usr/bin/env node

const { callModel } = require('../core/model_call');
const { createModelRuntime } = require('../core/model_runtime');
const { BACKENDS, TASK_CLASSES } = require('../core/model_constants');
const ModelRouter = require('../core/router');

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

function makeProvider(overrides = {}) {
  return {
    health: overrides.health || (async () => ({ ok: true })),
    call: overrides.call || (async () => ({ text: 'ok', raw: {}, usage: null }))
  };
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
  const router = new ModelRouter({
    localFallbackEnabled: options.localFallbackEnabled || false
  });

  return createModelRuntime({
    persistLogs: false,
    router,
    providers: options.providers
  });
}

async function main() {
  let passCount = 0;
  let failCount = 0;

  const basicCase = await runCase('BASIC routes to Anthropic by default', async () => {
    global.__OPENCLAW_MODEL_RUNTIME = buildRuntime({
      providers: {
        [BACKENDS.OATH_CLAUDE]: makeProvider({
          call: async () => ({ text: 'oath', raw: {}, usage: null })
        }),
        [BACKENDS.ANTHROPIC_CLAUDE_API]: makeProvider({
          call: async () => ({ text: 'anthropic', raw: {}, usage: null })
        })
      }
    });

    const result = await callModel({
      taskId: 'verify_basic',
      messages: [{ role: 'user', content: 'list files in project' }],
      taskClass: TASK_CLASSES.BASIC,
      metadata: {}
    });

    assertEqual(result.backend, BACKENDS.ANTHROPIC_CLAUDE_API, 'backend');
  });

  if (basicCase) {
    passCount += 1;
  } else {
    failCount += 1;
  }

  const healthyCase = await runCase('NON_BASIC routes to Anthropic when healthy', async () => {
    global.__OPENCLAW_MODEL_RUNTIME = buildRuntime({
      providers: {
        [BACKENDS.OATH_CLAUDE]: makeProvider({
          call: async () => ({ text: 'oath-ok', raw: {}, usage: { totalTokens: 5 } })
        }),
        [BACKENDS.ANTHROPIC_CLAUDE_API]: makeProvider({
          call: async () => ({ text: 'anthropic-ok', raw: {}, usage: { totalTokens: 5 } })
        })
      }
    });

    const result = await callModel({
      taskId: 'verify_nonbasic_healthy',
      messages: [{ role: 'user', content: 'propose architecture changes' }],
      taskClass: TASK_CLASSES.NON_BASIC,
      metadata: {}
    });

    assertEqual(result.backend, BACKENDS.ANTHROPIC_CLAUDE_API, 'backend');
  });

  if (healthyCase) {
    passCount += 1;
  } else {
    failCount += 1;
  }

  const oathFailureCase = await runCase('Anthropic AUTH failure falls back to OATH', async () => {
    global.__OPENCLAW_MODEL_RUNTIME = buildRuntime({
      providers: {
        [BACKENDS.OATH_CLAUDE]: makeProvider({
          call: async () => ({ text: 'oath-ok', raw: {}, usage: { totalTokens: 5 } })
        }),
        [BACKENDS.ANTHROPIC_CLAUDE_API]: makeProvider({
          call: async () => {
            const error = new Error('authentication_error');
            error.status = 401;
            error.code = 'authentication_error';
            throw error;
          }
        })
      }
    });

    const result = await callModel({
      taskId: 'verify_oath_auth',
      messages: [{ role: 'user', content: 'complex debugging with invariants' }],
      taskClass: TASK_CLASSES.NON_BASIC,
      metadata: {}
    });

    assertEqual(result.backend, BACKENDS.OATH_CLAUDE, 'backend');
    if (!hasRouteSelect(result.events, BACKENDS.OATH_CLAUDE)) {
      throw new Error('expected ROUTE_SELECT event for OATH fallback');
    }
  });

  if (oathFailureCase) {
    passCount += 1;
  } else {
    failCount += 1;
  }

  const oathRateLimitCase = await runCase(
    'Anthropic RATE_LIMIT failure falls back to OATH',
    async () => {
      global.__OPENCLAW_MODEL_RUNTIME = buildRuntime({
        providers: {
          [BACKENDS.OATH_CLAUDE]: makeProvider({
            call: async () => ({ text: 'oath-ok', raw: {}, usage: { totalTokens: 5 } })
          }),
          [BACKENDS.ANTHROPIC_CLAUDE_API]: makeProvider({
            call: async () => {
              const error = new Error('rate_limit');
              error.status = 429;
              error.code = 'rate_limit';
              throw error;
            }
          })
        }
      });

      const result = await callModel({
        taskId: 'verify_oath_rate_limit',
        messages: [{ role: 'user', content: 'deep reasoning architecture task' }],
        taskClass: TASK_CLASSES.NON_BASIC,
        metadata: {}
      });

      assertEqual(result.backend, BACKENDS.OATH_CLAUDE, 'backend');
    }
  );

  if (oathRateLimitCase) {
    passCount += 1;
  } else {
    failCount += 1;
  }

  const anthropicFailureCase = await runCase(
    'Anthropic missing key falls back to OATH',
    async () => {
      global.__OPENCLAW_MODEL_RUNTIME = buildRuntime({
        providers: {
          [BACKENDS.OATH_CLAUDE]: makeProvider({
            call: async () => ({ text: 'oath-ok', raw: {}, usage: { totalTokens: 5 } })
          }),
          [BACKENDS.ANTHROPIC_CLAUDE_API]: makeProvider({
            health: async () => ({ ok: false, reason: 'missing_api_key' })
          })
        }
      });

      const result = await callModel({
        taskId: 'verify_anthropic_missing_key',
        messages: [{ role: 'user', content: 'multi-file invariant refactor' }],
        taskClass: TASK_CLASSES.NON_BASIC,
        metadata: {}
      });

      assertEqual(result.backend, BACKENDS.OATH_CLAUDE, 'backend');
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
