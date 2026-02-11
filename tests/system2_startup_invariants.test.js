'use strict';

const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { probeStartupInvariants, sha256FileHex } = require('../core/system2/startup_invariants');

function run(name, fn) {
  try {
    fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    console.error(error.message);
    process.exit(1);
  }
}

run('startup invariants pass for valid config', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'system2-invariants-pass-'));
  const identityPath = path.join(tmpDir, 'IDENTITY.md');
  const allowlistPath = path.join(tmpDir, 'allowlist.json');
  fs.writeFileSync(identityPath, '# identity\n', 'utf8');
  fs.writeFileSync(allowlistPath, '{"tools":[]}\n', 'utf8');
  const hash = sha256FileHex(allowlistPath);

  const report = probeStartupInvariants({
    workspaceRoot: tmpDir,
    config: {
      system2: {
        workspace_path: '.',
        identity_path: 'IDENTITY.md',
        policy_version: '1.0.0',
        tool_allowlist_path: 'allowlist.json',
        tool_allowlist_hash: hash,
        envelope_signing_key_env: 'SYSTEM2_ENVELOPE_HMAC_KEY'
      },
      __meta: {}
    }
  });

  assert.strictEqual(report.ok, true);
});

run('startup invariants fail on allowlist hash mismatch', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'system2-invariants-fail-'));
  const identityPath = path.join(tmpDir, 'IDENTITY.md');
  const allowlistPath = path.join(tmpDir, 'allowlist.json');
  fs.writeFileSync(identityPath, '# identity\n', 'utf8');
  fs.writeFileSync(allowlistPath, '{"tools":[]}\n', 'utf8');

  const report = probeStartupInvariants({
    workspaceRoot: tmpDir,
    config: {
      system2: {
        workspace_path: '.',
        identity_path: 'IDENTITY.md',
        policy_version: '1.0.0',
        tool_allowlist_path: 'allowlist.json',
        tool_allowlist_hash: 'bad-hash',
        envelope_signing_key_env: 'SYSTEM2_ENVELOPE_HMAC_KEY'
      },
      __meta: {}
    }
  });

  assert.strictEqual(report.ok, false);
  assert.ok(report.checks.some((entry) => entry.name === 'tool_allowlist_hash_match' && entry.ok === false));
});
