'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const REPO_ROOT = path.resolve(__dirname, '..');
const SCRIPT_PATH = path.join(REPO_ROOT, 'scripts', 'install_tailscale_serve_launchagent.sh');

function runScript(home, overrides = {}) {
  return spawnSync('bash', [SCRIPT_PATH], {
    cwd: REPO_ROOT,
    env: { ...process.env, HOME: home, ...overrides },
    encoding: 'utf8',
  });
}

test('dryrun prints target plist path and launchagent payload', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'oc-ts-agent-home-'));
  const run = runScript(home, { OPENCLAW_TAILSCALE_SERVE_LAUNCHAGENT_DRYRUN: '1' });
  const output = `${run.stdout || ''}${run.stderr || ''}`;
  assert.equal(run.status, 0, output);
  assert.match(output, new RegExp(`PLIST_PATH=${home.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&')}/Library/LaunchAgents/ai\\.openclaw\\.tailscale-serve\\.plist`));
  assert.match(output, /<key>ProgramArguments<\/key>/);
  assert.match(output, /scripts\/tailscale_serve_openclaw\.sh/);

  const plistPath = path.join(home, 'Library', 'LaunchAgents', 'ai.openclaw.tailscale-serve.plist');
  assert.equal(fs.existsSync(plistPath), false);
});

test('write mode creates 0600 plist without applying launchctl', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'oc-ts-agent-home-'));
  const run = runScript(home);
  const output = `${run.stdout || ''}${run.stderr || ''}`;
  assert.equal(run.status, 0, output);
  assert.match(output, /WROTE_PLIST=/);
  assert.match(output, /LAUNCHCTL_APPLIED=0/);

  const plistPath = path.join(home, 'Library', 'LaunchAgents', 'ai.openclaw.tailscale-serve.plist');
  assert.equal(fs.existsSync(plistPath), true);
  const mode = fs.statSync(plistPath).mode & 0o777;
  assert.equal(mode, 0o600);

  const plist = fs.readFileSync(plistPath, 'utf8');
  assert.match(plist, /<string>ai\.openclaw\.tailscale-serve<\/string>/);
  assert.match(plist, /<string>\/bin\/zsh<\/string>/);
  assert.match(plist, /<string>-lc<\/string>/);
  assert.match(plist, /scripts\/tailscale_serve_openclaw\.sh/);
});
