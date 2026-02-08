const assert = require('assert');
const fs = require('fs');
const path = require('path');

// This test assumes any call path that triggers model_call will emit an audit line.
// We simulate by importing the helper directly.
const { appendAudit } = require('../core/prompt_audit');

function main() {
  const p = path.join(process.cwd(), 'logs', 'prompt_audit.jsonl');
  try {
    fs.unlinkSync(p);
  } catch (_) {}

  appendAudit({
    ts: Date.now(),
    backend: 'test',
    model: 'test-model',
    approxChars: 10,
    parts: { system: 1, instruction: 2, history: 3, state: 4, user: 0, scratch: 0 },
    hash: 'deadbeef'
  });

  const content = fs.readFileSync(p, 'utf8').trim();
  const obj = JSON.parse(content);

  assert.ok(obj.ts);
  assert.strictEqual(obj.backend, 'test');
  assert.strictEqual(obj.model, 'test-model');
  assert.strictEqual(obj.approxChars, 10);
  assert.ok(obj.parts);
  assert.ok(obj.hash);

  console.log('PASS prompt audit emits required fields');
}

main();
