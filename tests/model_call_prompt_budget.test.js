const assert = require('assert');
const fs = require('fs');
const path = require('path');

const { callModel } = require('../core/model_call');
const { BACKENDS } = require('../core/model_constants');
const { estimateMessagesChars } = require('../core/continuity_prompt');

const MAX_SYSTEM_PROMPT_CHARS = 12000;
const MAX_HISTORY_CHARS = 8000;
const MAX_TOTAL_INPUT_CHARS = 20000;
const STRICT_MAX_SYSTEM_PROMPT_CHARS = 8000;
const CONTROLLED_PROMPT_BLOCK_MESSAGE =
  "Context trimmed to safe limits. Please send 'continue' to proceed.";
const AUDIT_FILE = path.join(process.cwd(), 'logs', 'prompt_audit.jsonl');

function readAuditEntries() {
  if (!fs.existsSync(AUDIT_FILE)) {
    return [];
  }
  const text = fs.readFileSync(AUDIT_FILE, 'utf8').trim();
  if (!text) {
    return [];
  }
  return text.split('\n').map((line) => JSON.parse(line));
}

function historyChars(messages = []) {
  const safeMessages = Array.isArray(messages) ? messages : [];
  let latestUserIndex = -1;
  const conversational = [];

  safeMessages.forEach((message) => {
    if (!message || typeof message.content !== 'string') {
      return;
    }
    const role = String(message.role || 'user').toLowerCase();
    if (role === 'system') {
      return;
    }
    conversational.push(message);
    if (role === 'user') {
      latestUserIndex = conversational.length - 1;
    }
  });

  return conversational.reduce((sum, message, index) => {
    if (index === latestUserIndex) {
      return sum;
    }
    return sum + String(message.content || '').length;
  }, 0);
}

function latestUserContent(messages = []) {
  const list = [...messages].reverse();
  const found = list.find((message) => String(message?.role || '').toLowerCase() === 'user');
  return found && typeof found.content === 'string' ? found.content : '';
}

function firstSystemContent(messages = []) {
  const found = messages.find((message) => String(message?.role || '').toLowerCase() === 'system');
  return found && typeof found.content === 'string' ? found.content : '';
}

function createRuntime({ onCall, contextWindow } = {}) {
  const calls = [];

  const provider = {
    contextWindow,
    model: 'oath-test-model',
    async health() {
      return { ok: true };
    },
    async call(payload) {
      calls.push(payload);
      if (typeof onCall === 'function') {
        return onCall(payload, calls.length - 1);
      }
      return { text: 'ok', raw: { provider: 'oath' }, usage: null };
    }
  };

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
        [BACKENDS.OATH_CLAUDE]: provider
      }
    }
  };
}

async function withRuntime(options, fn) {
  const { runtime, calls } = createRuntime(options);
  global.__OPENCLAW_MODEL_RUNTIME = runtime;
  try {
    await fn(calls);
  } finally {
    delete global.__OPENCLAW_MODEL_RUNTIME;
  }
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

async function testSystemPromptCap() {
  await withRuntime({}, async (calls) => {
    const result = await callModel({
      taskId: 'budget_system_cap',
      taskClass: 'NON_BASIC',
      messages: [
        { role: 'system', content: 's'.repeat(14000) },
        { role: 'user', content: 'hello' }
      ],
      metadata: {}
    });

    assert.strictEqual(result.backend, BACKENDS.OATH_CLAUDE);
    assert.strictEqual(calls.length, 1, 'provider call should run once');

    const systemText = firstSystemContent(calls[0].messages);
    assert.ok(systemText.length <= MAX_SYSTEM_PROMPT_CHARS);
    assert.ok(systemText.includes('[TRUNCATED_SYSTEM_HEAD:'));
    assert.strictEqual(latestUserContent(calls[0].messages), 'hello');
  });
}

async function testHistoryCap() {
  await withRuntime({}, async (calls) => {
    await callModel({
      taskId: 'budget_history_cap',
      taskClass: 'NON_BASIC',
      messages: [
        { role: 'system', content: 'system' },
        { role: 'assistant', content: 'a'.repeat(12000) },
        { role: 'user', content: 'hello' }
      ],
      metadata: {}
    });

    assert.strictEqual(calls.length, 1, 'provider call should run once');
    assert.ok(historyChars(calls[0].messages) <= MAX_HISTORY_CHARS);
    assert.ok(historyChars(calls[0].messages) > 0);
  });
}

async function testTotalBudgetDropsHistoryBeforeStrictSystem() {
  await withRuntime({}, async (calls) => {
    await callModel({
      taskId: 'budget_total_cap',
      taskClass: 'NON_BASIC',
      messages: [
        { role: 'system', content: 's'.repeat(13000) },
        { role: 'assistant', content: 'h'.repeat(9000) },
        { role: 'user', content: 'hello' }
      ],
      metadata: {}
    });

    assert.strictEqual(calls.length, 1, 'provider call should run once');

    const finalMessages = calls[0].messages;
    const finalSystem = firstSystemContent(finalMessages);
    assert.ok(finalSystem.length <= MAX_SYSTEM_PROMPT_CHARS);
    assert.ok(finalSystem.length > STRICT_MAX_SYSTEM_PROMPT_CHARS);
    assert.strictEqual(historyChars(finalMessages), 0, 'history should be dropped first');
    assert.ok(estimateMessagesChars(finalMessages) <= MAX_TOTAL_INPUT_CHARS);
  });
}

async function testStrictSecondPassUsesSmallerCaps() {
  await withRuntime({ contextWindow: 10000 }, async (calls) => {
    const result = await callModel({
      taskId: 'budget_strict_second_pass',
      taskClass: 'NON_BASIC',
      messages: [
        { role: 'system', content: 'x'.repeat(9500) },
        { role: 'user', content: 'hello' }
      ],
      metadata: {}
    });

    assert.strictEqual(result.backend, BACKENDS.OATH_CLAUDE);
    assert.strictEqual(calls.length, 1, 'provider call should run once after strict pass');
    assert.ok(firstSystemContent(calls[0].messages).length <= STRICT_MAX_SYSTEM_PROMPT_CHARS);
  });
}

async function testControlledBlockSkipsProviderCall() {
  await withRuntime({ contextWindow: 1200 }, async (calls) => {
    const result = await callModel({
      taskId: 'budget_controlled_block',
      taskClass: 'NON_BASIC',
      messages: [{ role: 'user', content: 'u'.repeat(2000) }],
      metadata: {}
    });

    assert.strictEqual(calls.length, 0, 'provider call must be blocked');
    assert.strictEqual(result.response.text, CONTROLLED_PROMPT_BLOCK_MESSAGE);

    const blockedEvent = result.events.find(
      (entry) => entry && entry.event_type === 'BACKEND_ERROR' && entry.provider_error_code === 'prompt_budget_blocked'
    );
    assert.ok(blockedEvent, 'expected prompt budget blocked event');
  });
}

async function testAuditReflectsFinalIncludedSizes() {
  fs.mkdirSync(path.dirname(AUDIT_FILE), { recursive: true });
  try {
    fs.unlinkSync(AUDIT_FILE);
  } catch (_) {}

  await withRuntime({}, async () => {
    await callModel({
      taskId: 'budget_audit_truthful',
      taskClass: 'NON_BASIC',
      messages: [
        { role: 'system', content: 'system text' },
        { role: 'assistant', content: 'past' },
        { role: 'user', content: 'hello' }
      ],
      metadata: {
        projectContext: 'project context',
        nonProjectContext: 'non project context',
        projectContextIncluded: true,
        nonProjectContextIncluded: false
      }
    });
  });

  const entries = readAuditEntries();
  assert.ok(entries.length >= 3, 'expected prompt audit entries');
  const success = entries.reverse().find((entry) => entry && entry.attempt === 'success');
  assert.ok(success, 'expected success audit entry');
  assert.strictEqual(
    success.approxChars,
    success.parts.systemPrompt + success.parts.userPrompt + success.parts.history
  );
  assert.strictEqual(success.parts.projectContextIncludedChars, 'project context'.length);
  assert.strictEqual(success.parts.nonProjectContextIncludedChars, 0);
}

async function main() {
  await runTest('system prompt is capped', testSystemPromptCap);
  await runTest('history is capped by char budget', testHistoryCap);
  await runTest('history drops before strict system tightening', testTotalBudgetDropsHistoryBeforeStrictSystem);
  await runTest('strict second pass applies when near context window', testStrictSecondPassUsesSmallerCaps);
  await runTest('controlled block path skips provider call', testControlledBlockSkipsProviderCall);
  await runTest('audit reflects final included size fields', testAuditReflectsFinalIncludedSizes);
}

main().catch(() => {
  process.exit(1);
});
