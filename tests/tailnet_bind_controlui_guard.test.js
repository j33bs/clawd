'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawn, spawnSync } = require('node:child_process');

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

function extractOverlayPath(output) {
  const match = output.match(/OPENCLAW_CONFIG_PATH=([^\r\n]+)/);
  return match ? match[1].trim() : '';
}

test('bind=tailnet without explicit control_ui mode fails with guidance', () => {
  const run = runWrapper({
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

test('bind=tailnet control_ui=off dryrun prints command and defers overlay creation', () => {
  const run = runWrapper({
    OPENCLAW_GATEWAY_BIND: 'tailnet',
    OPENCLAW_TAILNET_CONTROL_UI: 'off',
    OPENCLAW_TAILSCALE_IP_OVERRIDE: '100.64.0.1',
    OPENCLAW_WRAPPER_DRYRUN: '1',
  });

  assert.equal(run.status, 0, run.output);
  assert.match(run.output, /OPENCLAW_TAILNET_BIND_HOST=100\.64\.0\.1/);
  assert.match(run.output, /OPENCLAW_TAILNET_CONTROL_UI_MECHANISM=overlay_config/);
  assert.match(run.output, /OPENCLAW_TAILNET_MODE bind=tailnet control_ui=off allowed_origins_count=0 dryrun=1/);
  assert.match(run.output, /OPENCLAW_WRAPPER_DRYRUN_COMMAND=.*openclaw .*gateway .*run/);
  assert.match(run.output, /--bind tailnet/);
  assert.equal(extractOverlayPath(run.output), '', 'dryrun must not create or print overlay path');
});

test('bind=tailnet control_ui=allowlist dryrun validates explicit origins and count only', () => {
  const run = runWrapper({
    OPENCLAW_GATEWAY_BIND: 'tailnet',
    OPENCLAW_TAILNET_CONTROL_UI: 'allowlist',
    OPENCLAW_TAILNET_ALLOWED_ORIGINS: 'http://100.64.0.1:18789, https://control.example.test:443',
    OPENCLAW_TAILSCALE_IP_OVERRIDE: '100.64.0.1',
    OPENCLAW_WRAPPER_DRYRUN: '1',
  });

  assert.equal(run.status, 0, run.output);
  assert.match(run.output, /OPENCLAW_TAILNET_MODE bind=tailnet control_ui=allowlist allowed_origins_count=2 dryrun=1/);
  assert.equal(extractOverlayPath(run.output), '', 'dryrun must not create or print overlay path');
});

function statPerm(pathname) {
  const bsd = spawnSync('stat', ['-f', '%Lp', pathname], { encoding: 'utf8' });
  if (bsd.status === 0) return (bsd.stdout || '').trim();
  const gnu = spawnSync('stat', ['-c', '%a', pathname], { encoding: 'utf8' });
  assert.equal(gnu.status, 0, gnu.stderr || gnu.stdout);
  return (gnu.stdout || '').trim();
}

test('allowlist non-dryrun test guard creates 0600 minimal overlay and cleans it on exit', async () => {
  const env = {
    ...process.env,
    OPENCLAW_GATEWAY_BIND: 'tailnet',
    OPENCLAW_TAILNET_CONTROL_UI: 'allowlist',
    OPENCLAW_TAILNET_ALLOWED_ORIGINS: 'http://100.64.0.1:18789',
    OPENCLAW_TAILSCALE_IP_OVERRIDE: '100.64.0.1',
    OPENCLAW_WRAPPER_DRYRUN: '0',
    OPENCLAW_WRAPPER_EXIT_AFTER_OVERLAY: '1',
    OPENCLAW_WRAPPER_TESTING: '1',
    NODE_ENV: 'test',
  };
  const child = spawn('bash', [WRAPPER_PATH], {
    cwd: REPO_ROOT,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  let output = '';
  child.stdout.setEncoding('utf8');
  child.stderr.setEncoding('utf8');
  child.stdout.on('data', (chunk) => {
    output += chunk;
  });
  child.stderr.on('data', (chunk) => {
    output += chunk;
  });

  const overlayPath = await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error(`timed out waiting for overlay path\n${output}`)), 5000);
    const check = () => {
      const found = extractOverlayPath(output);
      if (!found) return;
      clearTimeout(timeout);
      resolve(found);
    };
    child.stdout.on('data', check);
    child.stderr.on('data', check);
    child.on('error', (err) => {
      clearTimeout(timeout);
      reject(err);
    });
    child.on('exit', (code) => {
      if (extractOverlayPath(output)) return;
      clearTimeout(timeout);
      reject(new Error(`wrapper exited before printing overlay path (code=${code})\n${output}`));
    });
  });

  assert.ok(fs.existsSync(overlayPath), `expected overlay to exist during run: ${overlayPath}`);
  assert.equal(statPerm(overlayPath), '600');
  const overlay = JSON.parse(fs.readFileSync(overlayPath, 'utf8'));
  assert.deepEqual(Object.keys(overlay), ['gateway']);
  assert.deepEqual(Object.keys(overlay.gateway), ['controlUi']);
  assert.deepEqual(Object.keys(overlay.gateway.controlUi).sort(), ['allowedOrigins', 'enabled']);
  assert.equal(overlay.gateway.controlUi.enabled, true);
  assert.deepEqual(overlay.gateway.controlUi.allowedOrigins, ['http://100.64.0.1:18789']);

  const exitCode = await new Promise((resolve, reject) => {
    child.on('close', resolve);
    child.on('error', reject);
  });
  assert.equal(exitCode, 0, output);
  assert.equal(fs.existsSync(overlayPath), false, 'overlay should be removed by exit trap');
});
