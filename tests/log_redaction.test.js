'use strict';

// tests/log_redaction.test.js — CSA CCM v4 DSP-07, LOG-05

// ESM module — use dynamic import.
async function loadModule() {
  const { redactString, redactObjectKeys, sanitizeField } = await import(
    '../workspace/runtime_hardening/src/log.mjs'
  );
  return { redactString, redactObjectKeys, sanitizeField };
}

function run(name, fn) {
  try {
    fn();
    console.log(`  PASS ${name}`);
  } catch (err) {
    console.error(`  FAIL ${name}: ${err.message}`);
    process.exitCode = 1;
  }
}

const assert = require('node:assert/strict');

async function main() {
  const { redactString, redactObjectKeys, sanitizeField } = await loadModule();

  // ── Bearer / Authorization header ────────────────────────────────────────
  run('redacts Bearer token in Authorization header (case-insensitive)', () => {
    const out = redactString('Authorization: Bearer sk-abcdefghijklmnopqrstuvwxyz');
    assert.ok(!out.includes('sk-abcdefghijklmnopqrstuvwxyz'), `must not contain raw token, got: ${out}`);
    assert.ok(out.includes('<redacted>'), `must contain <redacted>, got: ${out}`);
  });

  run('redacts bare Bearer token', () => {
    const out = redactString('token: Bearer ghp_ABC123DEF456GHI789JKL012MNO345PQR678');
    assert.ok(!out.includes('ghp_'), `must not contain ghp_ prefix, got: ${out}`);
  });

  run('redacts Basic auth header value', () => {
    const out = redactString('Authorization: Basic dXNlcjpwYXNzd29yZA==');
    assert.ok(!out.includes('dXNlcjpwYXNzd29yZA=='), `must not contain base64 cred, got: ${out}`);
    assert.ok(out.includes('<redacted>'), `must contain <redacted>, got: ${out}`);
  });

  // ── Known token prefixes ──────────────────────────────────────────────────
  run('redacts sk- tokens (OpenAI / generic)', () => {
    const out = redactString('using key sk-abcdefghijklmnop');
    assert.ok(!out.includes('sk-abcdefghijklmnop'), `must redact sk- token, got: ${out}`);
    assert.ok(out.includes('<redacted-token>'), `must use <redacted-token>, got: ${out}`);
  });

  run('redacts gsk- tokens (Groq)', () => {
    const out = redactString('GROQ_API_KEY=gsk_abcdefghijklmnopqrstuvwxyz');
    assert.ok(!out.includes('gsk_abcdefghijklmnopqrstuvwxyz'), `must redact gsk_ token, got: ${out}`);
  });

  run('redacts xai- tokens (xAI / Grok)', () => {
    const out = redactString('key=xai-abcdefghijklmnopqrstuvwxyz1234');
    assert.ok(!out.includes('xai-abcdefghijklmnopqrstuvwxyz1234'), `must redact xai- token, got: ${out}`);
    assert.ok(out.includes('<redacted-token>'), `must use <redacted-token>, got: ${out}`);
  });

  // ya29. tokens embedded in a key=value line are caught by the generic
  // api_key/token/secret/password pattern (which runs first).  The raw
  // credential must be absent; the specific placeholder form may vary.
  run('redacts ya29. Google OAuth tokens (in key=value context)', () => {
    const out = redactString('access_token: ya29.abcdefghijklmnopqrstuvwxyz1234567890');
    assert.ok(
      !out.includes('ya29.abcdefghijklmnopqrstuvwxyz1234567890'),
      `must redact ya29. token, got: ${out}`
    );
    assert.ok(out.includes('<redacted>') || out.includes('<redacted-token>'), `must contain a redaction marker, got: ${out}`);
  });

  // ya29. tokens that appear standalone (no key= prefix) are caught by the
  // specific ya29 regex and marked as <redacted-token>.
  run('redacts bare ya29. Google OAuth tokens', () => {
    const out = redactString('passing ya29.abcdefghijklmnopqrstuvwxyz1234567890 to service');
    assert.ok(!out.includes('ya29.'), `must redact bare ya29. token, got: ${out}`);
    assert.ok(out.includes('<redacted-token>'), `must use <redacted-token> for bare token, got: ${out}`);
  });

  // GITHUB_TOKEN=ghp_... is caught by the generic `token=value` pattern;
  // raw credential must be absent regardless of placeholder form.
  run('redacts ghp_ GitHub personal access tokens in key=value context', () => {
    // 36 alphanumeric chars after ghp_ to satisfy specific regex if generic misses it.
    const out = redactString('GITHUB_TOKEN=ghp_AAAAABBBBBCCCCCDDDDDEEEEEFFFFF123456');
    assert.ok(!out.includes('ghp_'), `must redact ghp_ token, got: ${out}`);
  });

  // Standalone ghp_ tokens (36 chars) are caught by the specific regex.
  run('redacts standalone ghp_ GitHub personal access tokens', () => {
    // Exactly 36 chars after ghp_
    const out = redactString('token: ghp_AAAAABBBBBCCCCCDDDDDEEEEEFFFFFF12');
    assert.ok(!out.includes('ghp_AAAAABBBBBCCCCCDDDDDEEEEEFFFFFF12'), `must redact ghp_ token, got: ${out}`);
  });

  // Standalone ghr_ tokens (36 chars) are caught by the specific regex.
  run('redacts ghr_ GitHub refresh tokens', () => {
    // Exactly 36 alphanumeric chars after ghr_: 5+5+5+5+5+5+6 = 36
    const token = 'ghr_AAAAABBBBBCCCCCDDDDDEEEEEFFFFF123456';
    const out = redactString(`value=${token}`);
    assert.ok(!out.includes(token), `must redact ghr_ token, got: ${out}`);
    assert.ok(out.includes('<redacted-token>'), `must use <redacted-token> for standalone ghr_, got: ${out}`);
  });

  // ── OPENCLAW_ env var values ──────────────────────────────────────────────
  run('redacts OPENCLAW_ env var values', () => {
    const out = redactString('OPENCLAW_GATEWAY_TOKEN=super-secret-value-123');
    assert.ok(!out.includes('super-secret-value-123'), `must redact OPENCLAW_ value, got: ${out}`);
    assert.ok(out.includes('OPENCLAW_GATEWAY_TOKEN=<redacted>'), `must keep key name, got: ${out}`);
  });

  run('redacts OPENCLAW_ env var in log line', () => {
    const out = redactString('env OPENCLAW_API_KEY=abc123def456 passed to subprocess');
    assert.ok(!out.includes('abc123def456'), `must redact value, got: ${out}`);
  });

  // ── Generic key=value patterns ────────────────────────────────────────────
  run('redacts api_key=value patterns', () => {
    const out = redactString('api_key=my-secret-api-key-xyz');
    assert.ok(!out.includes('my-secret-api-key-xyz'), `must redact api_key value, got: ${out}`);
    assert.ok(out.includes('<redacted>'), `must contain <redacted>, got: ${out}`);
  });

  run('redacts password=value patterns', () => {
    const out = redactString('password=hunter2');
    assert.ok(!out.includes('hunter2'), `must redact password value, got: ${out}`);
  });

  run('does not redact innocuous strings', () => {
    const out = redactString('hello world, status=ok, count=42');
    assert.equal(out, 'hello world, status=ok, count=42', `must not modify innocuous strings, got: ${out}`);
  });

  // ── redactObjectKeys ──────────────────────────────────────────────────────
  run('redactObjectKeys: masks values of sensitive keys', () => {
    const obj = {
      username: 'alice',
      password: 'hunter2',
      apiKey: 'sk-secret',
      token: 'tok123',
      message: 'hello'
    };
    const out = redactObjectKeys(obj);
    assert.equal(out.username, 'alice', 'non-sensitive key must be preserved');
    assert.equal(out.message, 'hello', 'non-sensitive key must be preserved');
    assert.equal(out.password, '<redacted>', 'password must be redacted');
    assert.equal(out.apiKey, '<redacted>', 'apiKey must be redacted');
    assert.equal(out.token, '<redacted>', 'token must be redacted');
  });

  run('redactObjectKeys: returns non-objects unchanged', () => {
    assert.equal(redactObjectKeys(null), null);
    assert.equal(redactObjectKeys('string'), 'string');
    assert.deepEqual(redactObjectKeys([1, 2]), [1, 2]);
  });

  // ── sanitizeField with sensitive key names ────────────────────────────────
  run('sanitizeField: redacts sensitive keys in nested objects', () => {
    const out = sanitizeField({ user: { name: 'bob', secret: 'topsecret' } });
    assert.equal(out.user.name, 'bob');
    assert.equal(out.user.secret, '<redacted>');
  });

  run('sanitizeField: redacts xai- tokens in strings within objects', () => {
    const out = sanitizeField({ msg: 'key=xai-aaabbbcccdddeeefffggghhh1111' });
    assert.ok(!out.msg.includes('xai-'), `must redact xai- token in object string, got: ${out.msg}`);
  });

  console.log('PASS log_redaction all tests');
}

main().catch((err) => {
  console.error('FAIL', err);
  process.exitCode = 1;
});
