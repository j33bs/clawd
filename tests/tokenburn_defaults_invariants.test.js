#!/usr/bin/env node
'use strict';

const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { ProviderRegistry, _test: registryTest } = require('../core/system2/inference/provider_registry');
const { sanitizeToolOutputsForContext } = require('../core/system2/inference/tool_output_sanitizer');
const { TokenUsageLogger } = require('../core/system2/inference/token_usage_logger');

const tests = [];
function test(name, fn) {
  tests.push({ name, fn });
}

test('provider tier ordering defaults to enabled', function () {
  const candidates = [
    { provider_id: 'minimax-portal', model_id: 'MiniMax-M2.1' },
    { provider_id: 'groq', model_id: 'llama-3.3-70b-versatile' },
    { provider_id: 'local_vllm', model_id: 'AUTO_DISCOVER' }
  ];

  const ordered = registryTest.enforceProviderTierOrder(candidates, {});
  assert.strictEqual(ordered[0].provider_id, 'local_vllm');
  assert.strictEqual(ordered[1].provider_id, 'groq');
  assert.strictEqual(ordered[2].provider_id, 'minimax-portal');

  const disabled = registryTest.enforceProviderTierOrder(candidates, {
    OPENCLAW_ENFORCE_PROVIDER_TIER_ORDER: '0'
  });
  assert.deepStrictEqual(disabled, candidates);
});

test('local tier timeout has zero retries by default (fallback after first timeout)', async function () {
  const reg = new ProviderRegistry({
    env: {
      ENABLE_FREECOMPUTE_CLOUD: '1',
      OPENCLAW_GROQ_API_KEY: 'x'
    }
  });

  let localCalls = 0;
  let groqCalls = 0;

  reg._adapters.set('local_vllm', {
    async generationProbe() {
      return { ok: true };
    },
    async call() {
      localCalls += 1;
      const err = new Error('timeout connecting to local_vllm');
      err.code = 'PROVIDER_TIMEOUT';
      throw err;
    },
    async health() {
      return { ok: true, models: ['stub-model'] };
    }
  });

  reg._adapters.set('groq', {
    async call() {
      groqCalls += 1;
      return {
        text: 'ok',
        raw: {},
        usage: { inputTokens: 1, outputTokens: 1, totalTokens: 2, estimatedCostUsd: 0 }
      };
    },
    async health() {
      return { ok: true, models: ['stub-model'] };
    }
  });

  const result = await reg.dispatch({
    taskClass: 'fast_chat',
    messages: [{ role: 'user', content: 'ping' }]
  });

  assert.ok(result);
  assert.strictEqual(result.provider_id, 'groq');
  assert.strictEqual(localCalls, 1);
  assert.strictEqual(groqCalls, 1);
  reg.dispose();
});

test('tool sanitizer payload includes byte_size and bytes pointer fields', function () {
  const td = fs.mkdtempSync(path.join(os.tmpdir(), 'oc-inv-byte-'));
  const out = sanitizeToolOutputsForContext(
    [{ role: 'tool', name: 'exec', content: 'line1\nline2\nline3' }],
    {
      env: {
        OPENCLAW_TOOL_ARTIFACTS_DIR: td,
        OPENCLAW_RUN_ID: 'inv_bytes',
        OPENCLAW_TOOL_OUTPUT_MAX_CHARS: '2000'
      }
    }
  );

  const payload = JSON.parse(out.messages[0].content);
  assert.strictEqual(typeof payload.bytes, 'number');
  assert.strictEqual(typeof payload.byte_size, 'number');
  assert.strictEqual(payload.byte_size, payload.bytes);
  assert.ok(fs.existsSync(payload.artifact_path));
});

test('token logger JSONL row excludes raw prompt content keys', function () {
  const td = fs.mkdtempSync(path.join(os.tmpdir(), 'oc-inv-log-'));
  const logPath = path.join(td, 'token_usage.jsonl');
  const logger = new TokenUsageLogger({
    env: {
      OPENCLAW_TOKEN_USAGE_LOG_PATH: logPath,
      OPENCLAW_TOKENLOG_SAMPLE_RATE: '1.0'
    }
  });

  const wrote = logger.log({
    request_id: 'inv_req',
    provider: 'ollama',
    model: 'ollama/qwen2.5-coder:7b',
    prompt: 'secret prompt should never be logged',
    messages: [{ role: 'user', content: 'secret message should never be logged' }],
    tokens_in: 10,
    tokens_out: 5,
    total_tokens: 15,
    status: 'ok'
  });
  assert.strictEqual(wrote, true);

  const row = JSON.parse(fs.readFileSync(logPath, 'utf8').trim());
  assert.strictEqual(Object.prototype.hasOwnProperty.call(row, 'prompt'), false);
  assert.strictEqual(Object.prototype.hasOwnProperty.call(row, 'messages'), false);
});

test('sanitizer respects OPENCLAW_TOOL_OUTPUT_MAX_CHARS while preserving artifact pointering', function () {
  const td = fs.mkdtempSync(path.join(os.tmpdir(), 'oc-inv-maxchars-'));
  const maxChars = 220;
  const out = sanitizeToolOutputsForContext(
    [{ role: 'tool', name: 'exec', content: 'x'.repeat(18000) }],
    {
      env: {
        OPENCLAW_TOOL_ARTIFACTS_DIR: td,
        OPENCLAW_RUN_ID: 'inv_maxchars',
        OPENCLAW_TOOL_OUTPUT_MAX_CHARS: String(maxChars)
      }
    }
  );

  const toolMsg = out.messages[0];
  assert.ok(typeof toolMsg.content === 'string');
  assert.ok(toolMsg.content.length <= maxChars);
  assert.ok(toolMsg.content.includes('artifact_path'));
  assert.strictEqual(out.sanitized_count, 1);
  assert.strictEqual(out.artifacts.length, 1);
  assert.ok(fs.existsSync(out.artifacts[0].artifact_path));
});

async function run() {
  for (const t of tests) {
    try {
      await t.fn();
      console.log(`PASS ${t.name}`);
    } catch (err) {
      console.error(`FAIL ${t.name}: ${err.message}`);
      process.exitCode = 1;
    }
  }
}

run();
