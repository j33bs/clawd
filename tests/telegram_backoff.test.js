const assert = require('assert');

const TelegramClient = require('../core/telegram_client');

function makeResponse({ ok, status, payload }) {
  return {
    ok,
    status,
    json: async () => payload
  };
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

async function testRetriesOnFetchFailed() {
  let attempts = 0;
  const fetchFn = async () => {
    attempts += 1;
    if (attempts <= 2) {
      throw new Error('fetch failed');
    }
    return makeResponse({ ok: true, status: 200, payload: { ok: true } });
  };
  const sleepCalls = [];
  const client = new TelegramClient({
    token: 'test-token',
    fetchFn,
    sleepFn: async (ms) => {
      sleepCalls.push(ms);
    },
    maxRetriesSendMessage: 2
  });

  const result = await client.sendMessage({ chat_id: 1, text: 'hello' });
  assert.strictEqual(result.ok, true, 'expected sendMessage to succeed');
  assert.strictEqual(attempts, 3, 'expected 2 retries before success');
  assert.strictEqual(sleepCalls.length, 2, 'expected backoff sleeps');
}

async function testStopsOn4xx() {
  let attempts = 0;
  const fetchFn = async () => {
    attempts += 1;
    return makeResponse({
      ok: false,
      status: 400,
      payload: { ok: false, error_code: 400, description: 'bad request' }
    });
  };

  const client = new TelegramClient({
    token: 'test-token',
    fetchFn,
    sleepFn: async () => {},
    maxRetriesSendMessage: 4
  });

  const result = await client.sendMessage({ chat_id: 1, text: 'hello' });
  assert.strictEqual(result.ok, false, 'expected sendMessage to fail');
  assert.strictEqual(attempts, 1, 'expected no retries on 4xx');
}

async function main() {
  await runTest('telegram retries on fetch failed', testRetriesOnFetchFailed);
  await runTest('telegram stops on 4xx', testStopsOn4xx);
}

main().catch(() => {
  process.exit(1);
});
