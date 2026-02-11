'use strict';

const assert = require('node:assert');

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

function buildRuntime() {
  const router = new ModelRouter({
    localFallbackEnabled: true
  });

  return createModelRuntime({
    persistLogs: false,
    router,
    providers: {
      [BACKENDS.ANTHROPIC_CLAUDE_API]: makeProvider({
        call: async () => ({ text: 'anthropic-ok', raw: {}, usage: null })
      }),
      [BACKENDS.LOCAL_QWEN]: makeProvider({
        call: async () => ({ text: 'local-ok', raw: {}, usage: null })
      })
    }
  });
}

async function run(name, fn) {
  try {
    await fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    console.error(error.message);
    process.exit(1);
  }
}

async function main() {
  process.env.OPENCLAW_SYSTEM2_POLICY_ENFORCE = '1';
  global.__OPENCLAW_MODEL_RUNTIME = buildRuntime();

  await run('model_call denies when system2 policy sets deny_reason', async () => {
    const result = await callModel({
      taskId: 'system2_policy_deny',
      messages: [{ role: 'user', content: 'do heavy operation' }],
      taskClass: TASK_CLASSES.NON_BASIC,
      metadata: {
        system2_policy_input: {
          request_type: 'analysis',
          privacy_level: 'external_ok',
          budget: {
            remaining: 0,
            cap: 1000
          }
        }
      }
    });

    assert.ok(result.response.text.includes('Request denied by System-2 policy'));
    assert.ok(result.events.some((event) => event.provider_error_code === 'system2_policy_denied'));
  });

  await run('model_call keeps normal routing when system2 policy allows', async () => {
    const result = await callModel({
      taskId: 'system2_policy_allow',
      messages: [{ role: 'user', content: 'status summary' }],
      taskClass: TASK_CLASSES.BASIC,
      metadata: {
        system2_policy_input: {
          request_type: 'status',
          privacy_level: 'external_ok',
          budget: {
            remaining: 5000,
            cap: 10000
          }
        }
      }
    });

    assert.ok([BACKENDS.LOCAL_QWEN, BACKENDS.ANTHROPIC_CLAUDE_API].includes(result.backend));
  });
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
