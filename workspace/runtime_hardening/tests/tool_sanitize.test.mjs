import test from 'node:test';
import assert from 'node:assert/strict';

import { sanitizeToolInvocationOrThrow } from '../src/security/tool_sanitize.mjs';

test('tool sanitizer rejects oversized payload', () => {
  const payload = {
    name: 'exec_command',
    args: {
      cmd: 'x'.repeat(5000)
    }
  };

  assert.throws(
    () =>
      sanitizeToolInvocationOrThrow(payload, {
        limits: {
          maxStringLength: 1024,
          maxPayloadBytes: 2048
        }
      }),
    /tool payload rejected/
  );
});

test('tool sanitizer accepts bounded payload', () => {
  const payload = sanitizeToolInvocationOrThrow({
    name: 'exec_command',
    args: {
      cmd: 'echo ok',
      timeout_ms: 1000
    }
  });

  assert.equal(payload.name, 'exec_command');
  assert.equal(payload.args.cmd, 'echo ok');
});
