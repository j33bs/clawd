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

async function testMissingTokenFailsFast() {
  let attempts = 0;
  const fetchFn = async () => {
    attempts += 1;
    return makeResponse({ ok: true, status: 200, payload: { ok: true } });
  };
  const client = new TelegramClient({
    token: '',
    fetchFn
  });
  const result = await client.sendMessage({ chat_id: 1, text: 'hello' });
  assert.strictEqual(result.ok, false, 'expected missing token failure');
  assert.strictEqual(attempts, 0, 'expected no network call without token');
  assert.strictEqual(result.errorCategory, 'token_missing', 'expected token_missing category');
  assert.ok(String(result.error && result.error.message).includes('Token missing'), 'expected missing token message');
}

async function testMalformedTokenFailsFast() {
  let attempts = 0;
  const fetchFn = async () => {
    attempts += 1;
    return makeResponse({ ok: true, status: 200, payload: { ok: true } });
  };
  const client = new TelegramClient({
    token: '"bad token"\n',
    fetchFn
  });
  const result = await client.sendMessage({ chat_id: 1, text: 'hello' });
  assert.strictEqual(result.ok, false, 'expected malformed token failure');
  assert.strictEqual(attempts, 0, 'expected no network call for malformed token');
  assert.strictEqual(result.errorCategory, 'token_malformed', 'expected token_malformed category');
  assert.ok(String(result.error && result.error.message).includes('Token malformed'), 'expected malformed token message');
}

async function testClassifies401() {
  const client = new TelegramClient({
    token: 'test-token',
    fetchFn: async () =>
      makeResponse({
        ok: false,
        status: 401,
        payload: { ok: false, error_code: 401, description: 'Unauthorized' }
      })
  });

  const result = await client.sendMessage({ chat_id: 1, text: 'hello' });
  assert.strictEqual(result.ok, false, 'expected 401 failure');
  assert.strictEqual(result.errorCategory, 'token_rejected_401', 'expected 401 category');
  assert.ok(String(result.error && result.error.message).includes('401'), 'expected 401 message');
}

async function testClassifies404() {
  const client = new TelegramClient({
    token: 'test-token',
    fetchFn: async () =>
      makeResponse({
        ok: false,
        status: 404,
        payload: { ok: false, error_code: 404, description: 'Not Found' }
      })
  });

  const result = await client.sendMessage({ chat_id: 1, text: 'hello' });
  assert.strictEqual(result.ok, false, 'expected 404 failure');
  assert.strictEqual(result.errorCategory, 'endpoint_not_found_404', 'expected 404 category');
  assert.ok(String(result.error && result.error.message).includes('404'), 'expected 404 message');
}

async function main() {
  await runTest('telegram retries on fetch failed', testRetriesOnFetchFailed);
  await runTest('telegram stops on 4xx', testStopsOn4xx);
  await runTest('telegram missing token fails fast', testMissingTokenFailsFast);
  await runTest('telegram malformed token fails fast', testMalformedTokenFailsFast);
  await runTest('telegram classifies 401', testClassifies401);
  await runTest('telegram classifies 404', testClassifies404);
}

main().catch(() => {
  process.exit(1);
});
