const assert = require('assert');

const {
  redactToken,
  buildE2ESummary,
  sanitizeUpdateMeta,
  inspectToken,
  classifyTokenError,
  classifyHttpError
} = require('../scripts/telegram_diag');

if (process.env.TELEGRAM_E2E_TEST !== '1') {
  console.log('SKIP telegram e2e harness test (set TELEGRAM_E2E_TEST=1 to enable)');
  process.exit(0);
}

function runTest(name, fn) {
  try {
    fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    console.error(`  ${error.message}`);
    process.exit(1);
  }
}

runTest('redactToken removes token from output', () => {
  const token = '123456:ABCDEF';
  const input = `url=https://api.telegram.org/bot${token}/getMe`;
  const redacted = redactToken(input, token);
  assert.ok(!redacted.includes(token), 'token leaked in redacted text');
  assert.ok(redacted.includes('[REDACTED_TOKEN]'), 'missing redaction marker');
});

runTest('buildE2ESummary has required fields', () => {
  const summary = buildE2ESummary('live');
  const required = [
    'timestamp',
    'mode',
    'ok',
    'observed_update',
    'observed_reply',
    'latency_ms',
    'error_category'
  ];

  for (const field of required) {
    assert.ok(Object.prototype.hasOwnProperty.call(summary, field), `missing required field: ${field}`);
  }
  assert.strictEqual(summary.mode, 'live');
  assert.strictEqual(summary.ok, false);
});

runTest('sanitizeUpdateMeta strips message contents', () => {
  const update = {
    update_id: 42,
    message: {
      message_id: 99,
      chat: { id: 555 },
      from: { is_bot: false, username: 'user_should_not_escape' },
      text: 'sensitive text should not be returned',
      reply_to_message: { message_id: 88 }
    }
  };

  const meta = sanitizeUpdateMeta(update);
  assert.deepStrictEqual(meta, {
    update_id: 42,
    kind: 'message',
    chat_id: 555,
    message_id: 99,
    from_is_bot: false,
    has_text: true,
    reply_to_message_id: 88
  });
  assert.strictEqual(Object.prototype.hasOwnProperty.call(meta, 'text'), false, 'sanitized meta contains text');
  assert.strictEqual(Object.prototype.hasOwnProperty.call(meta, 'username'), false, 'sanitized meta contains username');
});

runTest('token/http classification taxonomy is stable', () => {
  const malformed = inspectToken(' "bad\n" ');
  assert.strictEqual(classifyTokenError(malformed), 'token_malformed');
  assert.strictEqual(classifyTokenError(inspectToken('')), 'token_missing');
  assert.strictEqual(classifyHttpError(401), 'token_rejected_401');
  assert.strictEqual(classifyHttpError(404), 'endpoint_not_found_404');
});
