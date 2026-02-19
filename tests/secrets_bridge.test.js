#!/usr/bin/env node
'use strict';

const assert = require('node:assert');

const {
  SecretsBridge,
  PROVIDER_ENV_MAP,
  BACKEND_TYPES,
  maskSecretFingerprint
} = require('../core/system2/inference/secrets_bridge');
const { REDACT_ENV_VARS, redactIfSensitive, loadFreeComputeConfig } = require('../core/system2/inference/config');

function test(name, fn) {
  try {
    fn();
    console.log('PASS ' + name);
  } catch (error) {
    console.error('FAIL ' + name + ': ' + error.message);
    process.exitCode = 1;
  }
}

test('provider mapping exposes required env vars', function () {
  assert.equal(PROVIDER_ENV_MAP.groq.envVar, 'OPENCLAW_GROQ_API_KEY');
  assert.equal(PROVIDER_ENV_MAP.gemini.envVar, 'OPENCLAW_GEMINI_API_KEY');
  assert.equal(PROVIDER_ENV_MAP.openrouter.envVar, 'OPENCLAW_OPENROUTER_API_KEY');
  assert.equal(PROVIDER_ENV_MAP['minimax-portal'].envVar, 'OPENCLAW_MINIMAX_PORTAL_API_KEY');
  assert.equal(PROVIDER_ENV_MAP.qwen.envVar, 'OPENCLAW_QWEN_API_KEY');
  assert.equal(PROVIDER_ENV_MAP.vllm.envVar, 'OPENCLAW_VLLM_API_KEY');
});

test('maskSecretFingerprint never returns raw secret value', function () {
  const secret = 'test-secret-value-123456';
  const masked = maskSecretFingerprint(secret);
  assert.ok(masked.includes('…'));
  assert.ok(!masked.includes(secret));
  assert.ok(masked.endsWith(secret.slice(-4)));
});

test('bridge serialization does not expose env secret values', function () {
  const env = {
    ENABLE_SECRETS_BRIDGE: '1',
    OPENCLAW_GROQ_API_KEY: 'EXAMPLE_API_KEY'
  };
  const bridge = new SecretsBridge({ env, backendAdapter: {} });
  const json = JSON.stringify(bridge);
  assert.ok(!json.includes('gsk_sensitive_test_secret'));
});

test('injectRuntimeEnv respects operator override and injects missing', function () {
  const env = {
    ENABLE_SECRETS_BRIDGE: '1',
    OPENCLAW_GEMINI_API_KEY: 'operator-override'
  };
  const secretMap = {
    groq: 'gsk_injected',
    gemini: 'gemini-stored'
  };
  const bridge = new SecretsBridge({
    env,
    backendAdapter: {
      get(providerId) {
        return secretMap[providerId] || null;
      }
    }
  });

  const target = { ...env };
  const result = bridge.injectRuntimeEnv(target);
  assert.equal(target.OPENCLAW_GROQ_API_KEY, 'gsk_injected');
  assert.equal(target.GROQ_API_KEY, 'gsk_injected');
  assert.equal(target.OPENCLAW_GEMINI_API_KEY, 'operator-override');
  assert.ok(result.injected.some((item) => item.provider === 'groq'));
  assert.ok(result.skipped.some((item) => item.provider === 'gemini' && item.reason === 'operator_override'));
});

test('injectRuntimeEnv propagates GROQ_API_KEY operator override to OPENCLAW_GROQ_API_KEY', function () {
  const env = {
    ENABLE_SECRETS_BRIDGE: '1',
    GROQ_API_KEY: 'operator-override'
  };
  const bridge = new SecretsBridge({
    env,
    backendAdapter: {
      get() {
        return 'gsk_injected';
      }
    }
  });

  const target = { ...env };
  const result = bridge.injectRuntimeEnv(target);
  assert.equal(target.GROQ_API_KEY, 'operator-override');
  assert.equal(target.OPENCLAW_GROQ_API_KEY, 'operator-override');
  assert.ok(result.skipped.some((item) => item.provider === 'groq' && item.reason === 'operator_override'));
});

test('config includes secrets bridge governance knobs', function () {
  const cfg = loadFreeComputeConfig({
    ENABLE_SECRETS_BRIDGE: '1',
    SECRETS_BACKEND: 'keychain',
    SECRETS_ALLOW_UI_INTAKE: '1',
    SECRETS_UI_LOCALHOST_ONLY: '1'
  });
  assert.equal(cfg.secretsBridge.enabled, true);
  assert.equal(cfg.secretsBridge.backend, 'keychain');
  assert.equal(cfg.secretsBridge.allowUiIntake, true);
  assert.equal(cfg.secretsBridge.uiLocalhostOnly, true);
});

test('redaction covers mapped secret env vars', function () {
  for (const providerId of Object.keys(PROVIDER_ENV_MAP)) {
    const envVar = PROVIDER_ENV_MAP[providerId].envVar;
    assert.ok(REDACT_ENV_VARS.includes(envVar), `${envVar} missing from redaction allowlist`);
    assert.equal(redactIfSensitive(envVar, 'secret'), '[REDACTED]');
  }
});

test('auto backend detection is platform deterministic', function () {
  const env = { ENABLE_SECRETS_BRIDGE: '1', SECRETS_BACKEND: 'auto' };
  const darwin = new SecretsBridge({ env, platform: 'darwin', backendAdapter: {} });
  const linux = new SecretsBridge({ env, platform: 'linux', backendAdapter: {} });
  const win = new SecretsBridge({ env, platform: 'win32', backendAdapter: {} });
  assert.equal(darwin.detectBackend(), BACKEND_TYPES.KEYCHAIN);
  assert.equal(linux.detectBackend(), BACKEND_TYPES.SECRETSERVICE);
  assert.equal(win.detectBackend(), BACKEND_TYPES.CREDMAN);
});

test('file backend requires explicit opt-in', function () {
  const bridge = new SecretsBridge({
    env: { ENABLE_SECRETS_BRIDGE: '1', SECRETS_BACKEND: 'auto' },
    platform: 'freebsd'
  });
  assert.throws(function () {
    bridge.setSecret('groq', 'x', { passphrase: 'passphrase' });
  }, /explicit opt-in/);
});
