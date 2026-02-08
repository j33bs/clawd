const assert = require('assert');
const fs = require('fs');
const path = require('path');

const { callModel } = require('../core/model_call');
const { BACKENDS } = require('../core/model_constants');

const AUDIT_FILE = path.join(process.cwd(), 'logs', 'prompt_audit.jsonl');

function readAuditEntries() {
  const text = fs.readFileSync(AUDIT_FILE, 'utf8').trim();
  if (!text) {
    return [];
  }
  return text.split('\n').map((line) => JSON.parse(line));
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

async function testCallModelWritesPromptAuditPhases() {
  fs.mkdirSync(path.dirname(AUDIT_FILE), { recursive: true });
  try {
    fs.unlinkSync(AUDIT_FILE);
  } catch (_) {}

  global.__OPENCLAW_MODEL_RUNTIME = {
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
        async call() {
          return {
            text: 'ok',
            usage: { input_tokens: 1, output_tokens: 1 }
          };
        }
      }
    }
  };

  const result = await callModel({
    taskId: 'task_prompt_audit',
    taskClass: 'NON_BASIC',
    messages: [
      { role: 'system', content: 'system text' },
      { role: 'assistant', content: 'previous answer' },
      { role: 'user', content: 'hello' }
    ],
    metadata: {
      projectContext: 'project context',
      nonProjectContext: 'non project context',
      projectContextIncluded: false,
      nonProjectContextIncluded: true
    }
  });

  assert.strictEqual(result.backend, BACKENDS.OATH_CLAUDE);

  const entries = readAuditEntries();
  assert.strictEqual(entries.length, 3, 'expected prepare, before_call, and success records');

  const phases = entries.map((entry) => entry.phase);
  assert.deepStrictEqual(phases, ['embedded_prompt_before', 'before_call', 'embedded_attempt']);

  const attempts = entries.map((entry) => entry.attempt);
  assert.deepStrictEqual(attempts, ['prepare', 'provider_call', 'success']);

  for (const entry of entries) {
    assert.ok(typeof entry.ts === 'number');
    assert.strictEqual(entry.backend, BACKENDS.OATH_CLAUDE);
    assert.strictEqual(entry.model, 'oath-test-model');
    assert.ok(entry.parts);
    assert.strictEqual(
      entry.approxChars,
      entry.parts.systemPrompt + entry.parts.userPrompt + entry.parts.history,
      'approxChars should equal included size parts'
    );
    assert.strictEqual(entry.parts.projectContextSource, 'project context'.length);
    assert.strictEqual(entry.parts.projectContextIncluded, false);
    assert.strictEqual(entry.parts.projectContextIncludedChars, 0);
    assert.strictEqual(entry.parts.nonProjectContextIncluded, true);
    assert.strictEqual(
      entry.parts.nonProjectContextIncludedChars,
      'non project context'.length
    );
    assert.ok(typeof entry.hash === 'string' && entry.hash.length > 0);
  }

  delete global.__OPENCLAW_MODEL_RUNTIME;
}

async function main() {
  await runTest('callModel emits phase-based prompt audit entries', testCallModelWritesPromptAuditPhases);
}

main().catch(() => {
  delete global.__OPENCLAW_MODEL_RUNTIME;
  process.exit(1);
});
