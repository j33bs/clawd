const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const assert = require('node:assert');
const { spawnSync } = require('node:child_process');

const repoRoot = path.resolve(__dirname, '..');
const runner = path.join(repoRoot, 'scripts', 'run_openclaw_gateway_repo_dali.sh');

function mkTempHarness() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'gateway-runner-test-'));
  const capture = path.join(dir, 'argv.txt');
  const fakeBin = path.join(dir, 'openclaw');
  fs.writeFileSync(
    fakeBin,
    `#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$@" > "${capture}"
`,
    { mode: 0o755 }
  );
  return { dir, capture, fakeBin };
}

function runRunner(extraEnv = {}, args = []) {
  const harness = mkTempHarness();
  const env = {
    ...process.env,
    OPENCLAW_BIN: harness.fakeBin,
    OPENCLAW_GATEWAY_SKIP_WORKTREE_GUARD: '1',
    OPENCLAW_GATEWAY_HARDEN_PATCH_MODE: 'skip',
    OPENCLAW_GATEWAY_BIND_MODE: 'loopback',
    OPENCLAW_GATEWAY_AUTH_MODE: '',
    OPENCLAW_GATEWAY_TOKEN: '',
    OPENCLAW_GATEWAY_PASSWORD: '',
    OPENCLAW_GATEWAY_PORT: '18789',
    OPENCLAW_CONTROL_UI_ALLOWED_ORIGINS: '',
    OPENCLAW_GATEWAY_ALLOW_NONLOOPBACK: '0',
    ...extraEnv
  };
  const result = spawnSync('bash', [runner, ...args], {
    cwd: repoRoot,
    env,
    encoding: 'utf8'
  });
  let argv = [];
  if (fs.existsSync(harness.capture)) {
    argv = fs.readFileSync(harness.capture, 'utf8').trim().split('\n').filter(Boolean);
  }
  fs.rmSync(harness.dir, { recursive: true, force: true });
  return { result, argv };
}

function assertFailed(result, msg) {
  assert.notStrictEqual(result.status, 0, msg);
}

function main() {
  {
    const { result, argv } = runRunner({}, ['--verbose']);
    assert.strictEqual(result.status, 0, `expected success, stderr=${result.stderr}`);
    assert.deepStrictEqual(argv.slice(0, 5), ['gateway', '--port', '18789', '--bind', 'loopback']);
    assert.ok(argv.includes('--verbose'), 'expected passthrough argument');
  }

  {
    const { result } = runRunner({
      OPENCLAW_CONTROL_UI_ALLOWED_ORIGINS: 'https://*.tail.example'
    });
    assertFailed(result, 'wildcard control-ui origin must be rejected');
    assert.match(result.stderr, /rejects wildcard origin/i);
  }

  {
    const { result } = runRunner({
      OPENCLAW_GATEWAY_BIND_MODE: 'tailnet'
    });
    assertFailed(result, 'tailnet bind requires explicit non-loopback ack');
    assert.match(result.stderr, /OPENCLAW_GATEWAY_ALLOW_NONLOOPBACK=1/i);
  }

  {
    const { result } = runRunner({
      OPENCLAW_GATEWAY_BIND_MODE: 'tailnet',
      OPENCLAW_GATEWAY_ALLOW_NONLOOPBACK: '1'
    });
    assertFailed(result, 'token auth must require OPENCLAW_GATEWAY_TOKEN');
    assert.match(result.stderr, /OPENCLAW_GATEWAY_TOKEN is required/i);
  }

  {
    const { result, argv } = runRunner({
      OPENCLAW_GATEWAY_BIND_MODE: 'tailnet',
      OPENCLAW_GATEWAY_ALLOW_NONLOOPBACK: '1',
      OPENCLAW_GATEWAY_TOKEN: 'test-token'
    });
    assert.strictEqual(result.status, 0, `expected success, stderr=${result.stderr}`);
    const joined = argv.join(' ');
    assert.match(joined, /--bind tailnet/);
    assert.match(joined, /--auth token/);
    assert.match(joined, /--token test-token/);
  }

  // Phase 1: config injection — OPENCLAW_CONTROL_UI_ALLOWED_ORIGINS produces config override file.
  {
    const overridePath = path.join(os.tmpdir(), `gateway-config-override-${Date.now()}.json`);
    const { result, argv } = runRunner({
      OPENCLAW_CONTROL_UI_ALLOWED_ORIGINS: 'https://dashboard.tail.example',
      OPENCLAW_CONFIG_OVERRIDE_PATH: overridePath
    });
    assert.strictEqual(result.status, 0, `config injection: expected success, stderr=${result.stderr}`);
    assert.ok(fs.existsSync(overridePath), 'config injection: override file must be written');
    const override = JSON.parse(fs.readFileSync(overridePath, 'utf8'));
    assert.deepStrictEqual(
      override,
      { gateway: { controlUi: { allowedOrigins: ['https://dashboard.tail.example'] } } },
      'config injection: override JSON must match expected shape'
    );
    assert.ok(argv.includes('--config-override'), 'config injection: --config-override must be passed to openclaw');
    fs.rmSync(overridePath, { force: true });
  }

  // Phase 1: config injection rejects wildcard origins.
  {
    const overridePath = path.join(os.tmpdir(), `gateway-config-override-wc-${Date.now()}.json`);
    const { result } = runRunner({
      OPENCLAW_CONTROL_UI_ALLOWED_ORIGINS: 'https://*.bad.example',
      OPENCLAW_CONFIG_OVERRIDE_PATH: overridePath
    });
    assertFailed(result, 'config injection: wildcard origin must be rejected');
    assert.match(result.stderr, /wildcard/i);
    fs.rmSync(overridePath, { force: true });
  }

  console.log('PASS run_openclaw_gateway_repo_dali hardening guards');
}

main();
