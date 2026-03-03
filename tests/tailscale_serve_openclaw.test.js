'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const REPO_ROOT = path.resolve(__dirname, '..');
const SCRIPT_PATH = path.join(REPO_ROOT, 'scripts', 'tailscale_serve_openclaw.sh');

function runScript(envOverrides = {}) {
  return spawnSync('bash', [SCRIPT_PATH], {
    cwd: REPO_ROOT,
    env: { ...process.env, ...envOverrides },
    encoding: 'utf8',
  });
}

test('dryrun emits explicit path-based tailscale serve command', () => {
  const run = runScript({ OPENCLAW_TAILSCALE_SERVE_DRYRUN: '1' });
  const output = `${run.stdout || ''}${run.stderr || ''}`;
  assert.equal(run.status, 0, output);
  assert.match(
    output,
    /OPENCLAW_TAILSCALE_SERVE_DRYRUN_COMMAND=.*serve .*--yes .*--bg .*--https=443 .*\/ .*http:\/\/127\.0\.0\.1:18789/
  );
});

test('non-loopback gateway host is rejected', () => {
  const run = runScript({
    OPENCLAW_TAILSCALE_SERVE_DRYRUN: '1',
    OPENCLAW_GATEWAY_HOST: '192.168.0.10',
  });
  const output = `${run.stdout || ''}${run.stderr || ''}`;
  assert.notEqual(run.status, 0);
  assert.match(output, /must stay loopback-only/);
});

test('script calls tailscale serve and tailscale serve status', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'oc-ts-serve-'));
  const logPath = path.join(dir, 'tailscale.log');
  const fakePath = path.join(dir, 'tailscale');
  fs.writeFileSync(
    fakePath,
    `#!/usr/bin/env bash
set -euo pipefail
echo "CALL:$*" >> "${logPath}"
if [[ "$1" == "serve" && "$2" == "status" ]]; then
  echo "status-ok"
  exit 0
fi
echo "serve-ok"
`,
    { mode: 0o755 }
  );

  const run = runScript({ TAILSCALE_BIN: fakePath });
  const output = `${run.stdout || ''}${run.stderr || ''}`;
  assert.equal(run.status, 0, output);

  const calls = fs.readFileSync(logPath, 'utf8').trim().split('\n');
  assert.equal(calls.length, 2);
  assert.match(calls[0], /^CALL:serve --yes --bg --https=443 \/ http:\/\/127\.0\.0\.1:18789$/);
  assert.match(calls[1], /^CALL:serve status$/);
});
