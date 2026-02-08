#!/usr/bin/env node
import assert from 'node:assert';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { callModel } = require('../core/model_call');
const { BACKENDS } = require('../core/model_constants');

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..');

function restoreEnv(previous) {
  for (const [key, value] of Object.entries(previous)) {
    if (value == null) {
      delete process.env[key];
    } else {
      process.env[key] = value;
    }
  }
}

async function main() {
  const previousEnv = {
    OPENCLAW_CONSTITUTION_ENFORCE: process.env.OPENCLAW_CONSTITUTION_ENFORCE,
    OPENCLAW_CONSTITUTION_SOURCE_PATH: process.env.OPENCLAW_CONSTITUTION_SOURCE_PATH,
    OPENCLAW_CONSTITUTION_SUPPORTING_PATHS: process.env.OPENCLAW_CONSTITUTION_SUPPORTING_PATHS,
    OPENCLAW_CONSTITUTION_MAX_CHARS: process.env.OPENCLAW_CONSTITUTION_MAX_CHARS
  };

  const sourcePath = path.join(repoRoot, 'SELF_IMPROVEMENT_CONSTITUTION.md');
  const supportingPaths = [
    path.join(repoRoot, 'notes/governance/2026-02-06-change-admission-gate-self-improvement.md'),
    path.join(repoRoot, 'AGENTS.md')
  ].join(path.delimiter);

  const calls = [];
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
        model: 'oath-smoke-model',
        async health() {
          return { ok: true };
        },
        async call(payload) {
          calls.push(payload);
          return { text: 'ok', raw: { provider: 'oath-smoke' }, usage: null };
        }
      }
    }
  };

  try {
    process.env.OPENCLAW_CONSTITUTION_ENFORCE = '1';
    process.env.OPENCLAW_CONSTITUTION_SOURCE_PATH = sourcePath;
    process.env.OPENCLAW_CONSTITUTION_SUPPORTING_PATHS = supportingPaths;
    process.env.OPENCLAW_CONSTITUTION_MAX_CHARS = '8000';

    const result = await callModel({
      taskId: 'constitution_operator_smoke',
      taskClass: 'NON_BASIC',
      messages: [
        { role: 'system', content: 'base system prompt' },
        { role: 'user', content: 'hello' }
      ],
      metadata: {}
    });

    assert.strictEqual(calls.length, 1, 'provider should be called exactly once');
    const outboundMessages = calls[0].messages || [];
    assert.ok(outboundMessages.length > 0, 'provider payload should include messages');
    assert.strictEqual(String(outboundMessages[0].role || '').toLowerCase(), 'system');

    const firstSystem = String(outboundMessages[0].content || '');
    const hasBegin = firstSystem.includes('[CONSTITUTION_BEGIN');
    const hasEnd = firstSystem.includes('[CONSTITUTION_END]');
    assert.ok(hasBegin && hasEnd, 'constitution block markers must be present');

    const controlledBlock = Boolean(result?.response?.raw?.controlled);
    assert.strictEqual(controlledBlock, false, 'controlled block should not trigger in smoke');

    console.log('ENABLEMENT_KNOB=OPENCLAW_CONSTITUTION_ENFORCE=1');
    console.log('ENTRYPOINT=core/model_call.callModel');
    console.log('PROVIDER_CALLED=1');
    console.log('INJECTION_ROLE=' + String(outboundMessages[0].role || ''));
    console.log('CONSTITUTION_MARKER_PRESENT=' + (hasBegin && hasEnd ? '1' : '0'));
    console.log('CONTROLLED_BLOCK=' + (controlledBlock ? '1' : '0'));
    console.log('RESULT=PASS');
  } finally {
    restoreEnv(previousEnv);
    delete global.__OPENCLAW_MODEL_RUNTIME;
  }
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : String(error));
  process.exit(1);
});
