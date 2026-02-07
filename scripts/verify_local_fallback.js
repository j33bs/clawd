#!/usr/bin/env node

const { callModel } = require('../core/model_call');
const { createModelRuntime } = require('../core/model_runtime');
const { BACKENDS, TASK_CLASSES } = require('../core/model_constants');
const ModelRouter = require('../core/router');
const {
  MAX_LOCAL_PROMPT_CHARS,
  estimateMessagesChars
} = require('../core/continuity_prompt');

function assertEqual(actual, expected, label) {
  if (actual !== expected) {
    throw new Error(`${label} expected ${expected}, got ${actual}`);
  }
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

function buildRuntime(providers) {
  const router = new ModelRouter({
    localFallbackEnabled: true,
    localBackends: [BACKENDS.LOCAL_OLLAMA]
  });

  return createModelRuntime({
    persistLogs: false,
    router,
    providers
  });
}

async function main() {
  let passCount = 0;
  let failCount = 0;

  const allowCase = await runCase('Rate limit falls back to local for summarize intent', async () => {
    let localCalls = 0;
    let receivedChars = 0;
    let receivedMessages = [];

    const largeChunk = 'x'.repeat(5000);
    const messages = [{ role: 'system', content: 'System prompt' }];
    for (let i = 0; i < 6; i += 1) {
      messages.push({ role: 'user', content: `User ${i} ${largeChunk}` });
      messages.push({ role: 'assistant', content: `Assistant ${i} ${largeChunk}` });
    }
    messages.push({ role: 'user', content: 'summarize the latest log' });

    const originalChars = estimateMessagesChars(messages);

    global.__OPENCLAW_MODEL_RUNTIME = buildRuntime({
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
        call: async ({ messages: received = [] }) => {
          localCalls += 1;
          receivedMessages = received;
          receivedChars = estimateMessagesChars(received);
          return { text: 'local-ok', raw: {}, usage: null };
        }
      })
    });

    const result = await callModel({
      taskId: 'verify_local_summarize',
      messages,
      taskClass: TASK_CLASSES.BASIC,
      metadata: {
        intent: 'summarize'
      }
    });

    assertEqual(result.backend, BACKENDS.LOCAL_OLLAMA, 'backend');
    assertEqual(localCalls, 1, 'local provider call count');
    if (receivedChars > MAX_LOCAL_PROMPT_CHARS) {
      throw new Error(`expected continuity prompt <= ${MAX_LOCAL_PROMPT_CHARS} chars`);
    }
    if (originalChars > MAX_LOCAL_PROMPT_CHARS) {
      const noteFound = receivedMessages.some((message) =>
        String(message.content || '').includes('Context truncated for continuity mode')
      );
      if (!noteFound) {
        throw new Error('expected continuity truncation note to be included');
      }
    }
  });

  if (allowCase) {
    passCount += 1;
  } else {
    failCount += 1;
  }

  const blockCase = await runCase('Local fallback blocked for research intent', async () => {
    let localCalls = 0;
    global.__OPENCLAW_MODEL_RUNTIME = buildRuntime({
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
    });

    let didThrow = false;
    try {
      await callModel({
        taskId: 'verify_local_blocked',
        messages: [{ role: 'user', content: 'research long form synthesis' }],
        taskClass: TASK_CLASSES.NON_BASIC,
        metadata: {
          intent: 'research'
        }
      });
    } catch (error) {
      didThrow = true;
      if (!error || error.code !== 'LOCAL_FALLBACK_DISALLOWED') {
        throw new Error('expected LOCAL_FALLBACK_DISALLOWED error');
      }
    }

    if (!didThrow) {
      throw new Error('expected local fallback to be blocked');
    }
    assertEqual(localCalls, 0, 'local provider call count');
  });

  if (blockCase) {
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
  console.error('FAIL verify_local_fallback');
  console.error(`  ${error.message}`);
  process.exit(1);
});
