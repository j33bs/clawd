#!/usr/bin/env node
'use strict';

const assert = require('node:assert/strict');

const {
  parseArgs,
  resolveTelegramToken,
  buildTelegramProbe,
  toPlain,
} = require('../scripts/openclaw_telegram_probe');

function run(name, fn) {
  Promise.resolve()
    .then(fn)
    .then(() => console.log(`PASS ${name}`))
    .catch((error) => {
      console.error(`FAIL ${name}: ${error.message}`);
      process.exitCode = 1;
    });
}

run('parseArgs detects --plain', () => {
  assert.equal(parseArgs([]).plain, false);
  assert.equal(parseArgs(['--plain']).plain, true);
});

run('resolveTelegramToken prefers env token', () => {
  const token = resolveTelegramToken({ TELEGRAM_BOT_TOKEN: 'abc123' }, null);
  assert.equal(token, 'abc123');
});

run('buildTelegramProbe handles missing token gracefully', async () => {
  const result = await buildTelegramProbe({
    env: {},
    configPath: '/definitely/missing/openclaw.json',
    fetchImpl: async () => {
      throw new Error('fetch should not be called without token');
    }
  });
  assert.equal(result.ok, false);
  assert.equal(result.error_code, 'telegram_token_missing');
});

run('buildTelegramProbe returns webhook details when API succeeds', async () => {
  const fakeFetch = async (url) => {
    if (url.includes('/getMe')) {
      return {
        status: 200,
        json: async () => ({ ok: true, result: { username: 'probe_bot' } })
      };
    }
    return {
      status: 200,
      json: async () => ({ ok: true, result: { url: 'https://example.invalid/hook', pending_update_count: 3 } })
    };
  };
  const result = await buildTelegramProbe({
    env: { TELEGRAM_BOT_TOKEN: 'abc123' },
    fetchImpl: fakeFetch
  });
  assert.equal(result.ok, true);
  assert.equal(result.bot_username, 'probe_bot');
  assert.equal(result.mode, 'webhook');
  assert.equal(result.pending_update_count, 3);
  assert.match(toPlain(result), /bot_username: probe_bot/);
});
