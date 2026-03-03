import test from 'node:test';
import assert from 'node:assert/strict';

import { retryWithBackoff } from '../src/retry_backoff.mjs';

test('retry wrapper retries on 429 and then succeeds', async () => {
  let attempts = 0;
  const delays = [];

  const result = await retryWithBackoff(
    async () => {
      attempts += 1;
      if (attempts < 3) {
        const error = new Error('rate limited');
        error.status = 429;
        throw error;
      }
      return { ok: true };
    },
    {
      maxAttempts: 3,
      baseDelayMs: 1,
      jitterMs: 0,
      sleep: async (ms) => {
        delays.push(ms);
      },
      rand: () => 0
    }
  );

  assert.equal(attempts, 3);
  assert.equal(delays.length, 2);
  assert.deepEqual(result, { ok: true });
});

test('retry wrapper stops after max attempts', async () => {
  let attempts = 0;

  await assert.rejects(
    () =>
      retryWithBackoff(
        async () => {
          attempts += 1;
          const error = new Error('server error');
          error.status = 500;
          throw error;
        },
        {
          maxAttempts: 3,
          baseDelayMs: 1,
          jitterMs: 0,
          sleep: async () => {},
          rand: () => 0
        }
      ),
    /server error/
  );

  assert.equal(attempts, 3);
});
