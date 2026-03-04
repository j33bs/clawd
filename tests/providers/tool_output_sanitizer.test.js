#!/usr/bin/env node
'use strict';

const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { sanitizeToolOutputsForContext } = require('../../core/system2/inference/tool_output_sanitizer');
const { TokenUsageLogger } = require('../../core/system2/inference/token_usage_logger');

const tests = [];
function test(name, fn) {
  tests.push({ name, fn });
}

test('sanitizeToolOutputsForContext writes artifact and injects stable pointer payload', function () {
  const td = fs.mkdtempSync(path.join(os.tmpdir(), 'oc-tool-sanitize-'));
  const messages = [
    { role: 'user', content: 'hi' },
    { role: 'tool', name: 'exec', content: Array.from({ length: 150 }, (_, i) => `line ${i + 1}`).join('\n') }
  ];

  const out = sanitizeToolOutputsForContext(messages, {
    env: {
      OPENCLAW_TOOL_ARTIFACTS_DIR: td,
      OPENCLAW_RUN_ID: 'unit_run',
      OPENCLAW_TOOL_OUTPUT_MAX_CHARS: '2000'
    }
  });

  assert.strictEqual(out.sanitized_count, 1);
  assert.strictEqual(out.total_tool_output_chars > 0, true);
  assert.strictEqual(out.artifacts.length, 1);
  assert.strictEqual(fs.existsSync(out.artifacts[0].artifact_path), true);

  const toolMsg = out.messages.find((m) => m.role === 'tool');
  assert.ok(toolMsg && typeof toolMsg.content === 'string');
  const payload = JSON.parse(toolMsg.content);
  assert.ok(payload.artifact_path);
  assert.ok(payload.sha256);
  assert.ok(payload.bytes > 0);
  assert.ok(payload.byte_size > 0);
  assert.strictEqual(payload.byte_size, payload.bytes);
  assert.ok(Object.prototype.hasOwnProperty.call(payload, 'preview_head'));
  assert.ok(Object.prototype.hasOwnProperty.call(payload, 'preview_tail'));
});

test('sanitizeToolOutputsForContext summarizes JSON payloads', function () {
  const td = fs.mkdtempSync(path.join(os.tmpdir(), 'oc-tool-json-'));
  const content = JSON.stringify({ items: [{ id: 1, title: 'a' }, { id: 2, title: 'b' }], ok: true });
  const out = sanitizeToolOutputsForContext(
    [{ role: 'tool', name: 'web.search', content }],
    {
      env: {
        OPENCLAW_TOOL_ARTIFACTS_DIR: td,
        OPENCLAW_RUN_ID: 'unit_json',
        OPENCLAW_TOOL_OUTPUT_MAX_CHARS: '2000'
      }
    }
  );
  const payload = JSON.parse(out.messages[0].content);
  assert.strictEqual(payload.format, 'json');
  assert.ok(payload.summary);
});

test('sanitizeToolOutputsForContext also sanitizes toolResult role payloads', function () {
  const td = fs.mkdtempSync(path.join(os.tmpdir(), 'oc-tool-role-'));
  const out = sanitizeToolOutputsForContext(
    [{ role: 'toolResult', name: 'web.search', content: 'x'.repeat(8000) }],
    {
      env: {
        OPENCLAW_TOOL_ARTIFACTS_DIR: td,
        OPENCLAW_RUN_ID: 'unit_toolresult',
        OPENCLAW_TOOL_OUTPUT_MAX_CHARS: '20000'
      }
    }
  );
  assert.strictEqual(out.sanitized_count, 1);
  const payload = JSON.parse(out.messages[0].content);
  assert.strictEqual(payload.tool, 'web.search');
  assert.ok(payload.artifact_path);
});

test('TokenUsageLogger writes redaction-safe JSONL rows', function () {
  const td = fs.mkdtempSync(path.join(os.tmpdir(), 'oc-token-log-'));
  const logPath = path.join(td, 'token_usage.jsonl');
  const logger = new TokenUsageLogger({
    env: {
      OPENCLAW_TOKEN_USAGE_LOG_PATH: logPath,
      OPENCLAW_TOKENLOG_SAMPLE_RATE: '1.0'
    }
  });

  const wrote = logger.log({
    request_id: 'req_123',
    agent_id: 'main',
    channel: 'telegram',
    provider: 'ollama',
    model: 'ollama/qwen2.5-coder:7b',
    reason_tag: 'fast_chat',
    prompt_chars: 1200,
    tool_output_chars: 7000,
    tokens_in: 300,
    tokens_out: 100,
    total_tokens: 400,
    cache_read_tokens: 0,
    cache_write_tokens: 0,
    latency_ms: 850,
    status: 'ok',
    prompt_hash: 'abc123'
  });
  assert.strictEqual(wrote, true);
  const lines = fs.readFileSync(logPath, 'utf8').trim().split(/\r?\n/);
  assert.strictEqual(lines.length, 1);
  const row = JSON.parse(lines[0]);
  assert.strictEqual(row.request_id, 'req_123');
  assert.strictEqual(row.total_tokens, 400);
  assert.strictEqual(row.prompt_hash, 'abc123');
  assert.strictEqual(Object.prototype.hasOwnProperty.call(row, 'prompt'), false);
});

test('TokenUsageLogger sampling=0 suppresses writes', function () {
  const td = fs.mkdtempSync(path.join(os.tmpdir(), 'oc-token-sample-'));
  const logPath = path.join(td, 'token_usage.jsonl');
  const logger = new TokenUsageLogger({
    env: {
      OPENCLAW_TOKEN_USAGE_LOG_PATH: logPath,
      OPENCLAW_TOKENLOG_SAMPLE_RATE: '0'
    }
  });

  const wrote = logger.log({ request_id: 'req_nope', total_tokens: 10, status: 'ok' });
  assert.strictEqual(wrote, false);
  assert.strictEqual(fs.existsSync(logPath), false);
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
