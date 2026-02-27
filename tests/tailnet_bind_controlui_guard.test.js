'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const REPO_ROOT = path.resolve(__dirname, '..');
const WRAPPER_PATH = path.join(REPO_ROOT, 'scripts', 'run_openclaw_gateway_repo.sh');

function runWrapper(envOverrides) {
  const child = spawnSync('bash', [WRAPPER_PATH], {
    cwd: REPO_ROOT,
    env: { ...process.env, ...envOverrides },
    encoding: 'utf8',
  });
  return {
    status: child.status,
    output: `${child.stdout || ''}${child.stderr || ''}`,
  };
}

function createBaseConfigDir() {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'openclaw-tailnet-'));
  const cfgPath = path.join(tmpDir, 'openclaw.json');
  fs.writeFileSync(cfgPath, '{}\n', 'utf8');
  return { tmpDir, cfgPath };
}

function extractOverlayPath(output) {
  const match = output.match(/OPENCLAW_CONFIG_PATH=([^\r\n]+)/);
  return match ? match[1].trim() : '';
}

test('bind=tailnet without explicit control_ui mode fails with guidance', () => {
  const { cfgPath } = createBaseConfigDir();
  const run = runWrapper({
    OPENCLAW_CONFIG_PATH: cfgPath,
    OPENCLAW_GATEWAY_BIND: 'tailnet',
    OPENCLAW_TAILSCALE_IP_OVERRIDE: '100.64.0.1',
    OPENCLAW_WRAPPER_DRYRUN: '1',
  });

  assert.notEqual(run.status, 0);
  assert.match(
    run.output,
    /tailnet bind requires OPENCLAW_TAILNET_CONTROL_UI=off OR allowlist \+ OPENCLAW_TAILNET_ALLOWED_ORIGINS/
  );
});

test('bind=tailnet control_ui=off dryrun prints command and writes overlay with controlUi disabled', () => {
  const { cfgPath } = createBaseConfigDir();
  const run = runWrapper({
    OPENCLAW_CONFIG_PATH: cfgPath,
    OPENCLAW_GATEWAY_BIND: 'tailnet',
    OPENCLAW_TAILNET_CONTROL_UI: 'off',
    OPENCLAW_TAILSCALE_IP_OVERRIDE: '100.64.0.1',
    OPENCLAW_WRAPPER_DRYRUN: '1',
  });

  assert.equal(run.status, 0, run.output);
  assert.match(run.output, /OPENCLAW_TAILNET_BIND_HOST=100\.64\.0\.1/);
  assert.match(run.output, /OPENCLAW_TAILNET_CONTROL_UI_MECHANISM=overlay_config/);
  assert.match(run.output, /OPENCLAW_WRAPPER_DRYRUN_COMMAND=.*openclaw .*gateway .*run/);
  assert.match(run.output, /--bind tailnet/);

  const overlayPath = extractOverlayPath(run.output);
  assert.ok(overlayPath.length > 0, 'expected OPENCLAW_CONFIG_PATH in output');
  const overlay = JSON.parse(fs.readFileSync(overlayPath, 'utf8'));
  assert.equal(overlay.gateway.controlUi.enabled, false);
});

test('bind=tailnet control_ui=allowlist writes exact allowedOrigins in overlay', () => {
  const { cfgPath } = createBaseConfigDir();
  const run = runWrapper({
    OPENCLAW_CONFIG_PATH: cfgPath,
    OPENCLAW_GATEWAY_BIND: 'tailnet',
    OPENCLAW_TAILNET_CONTROL_UI: 'allowlist',
    OPENCLAW_TAILNET_ALLOWED_ORIGINS: 'http://100.64.0.1:18789, https://control.example.test:443',
    OPENCLAW_TAILSCALE_IP_OVERRIDE: '100.64.0.1',
    OPENCLAW_WRAPPER_DRYRUN: '1',
  });

  assert.equal(run.status, 0, run.output);
  assert.match(run.output, /OPENCLAW_TAILNET_MODE bind=tailnet control_ui=allowlist allowed_origins_count=2/);
  const overlayPath = extractOverlayPath(run.output);
  assert.ok(overlayPath.length > 0, 'expected OPENCLAW_CONFIG_PATH in output');
  const overlay = JSON.parse(fs.readFileSync(overlayPath, 'utf8'));
  assert.deepEqual(overlay.gateway.controlUi.allowedOrigins, [
    'http://100.64.0.1:18789',
    'https://control.example.test:443',
  ]);
});
