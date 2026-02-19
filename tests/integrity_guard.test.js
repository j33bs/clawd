'use strict';

const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const {
  approveBaseline,
  assertNoRuntimeIdentityOverride,
  computeBaseline,
  createIntegrityGuard,
  verifyIntegrity
} = require('../core/system2/security/integrity_guard');

function mkRepoFixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'integrity-guard-'));
  fs.mkdirSync(path.join(root, '.git'));
  fs.mkdirSync(path.join(root, 'workspace', 'governance'), { recursive: true });
  fs.mkdirSync(path.join(root, 'workspace'), { recursive: true });

  fs.writeFileSync(path.join(root, 'workspace', 'CONSTITUTION.md'), 'constitution-v1\n', 'utf8');
  fs.writeFileSync(path.join(root, 'workspace', 'GOALS.md'), 'goals-v1\n', 'utf8');
  fs.writeFileSync(path.join(root, 'workspace', 'governance', 'IDENTITY.md'), 'identity-v1\n', 'utf8');
  fs.writeFileSync(path.join(root, 'workspace', 'governance', 'SOUL.md'), 'soul-v1\n', 'utf8');
  fs.writeFileSync(path.join(root, 'workspace', 'governance', 'USER.md'), 'user-v1\n', 'utf8');
  return root;
}

function testDeterministicBaseline() {
  const root = mkRepoFixture();
  const a = computeBaseline(root);
  const b = computeBaseline(root);
  assert.deepStrictEqual(a, b);
  console.log('PASS integrity baseline is deterministic');
}

function testDriftFailClosedAndApproval() {
  const root = mkRepoFixture();
  approveBaseline(root);

  assert.doesNotThrow(() => verifyIntegrity(root));

  fs.writeFileSync(path.join(root, 'workspace', 'governance', 'IDENTITY.md'), 'identity-v2\n', 'utf8');
  assert.throws(
    () => verifyIntegrity(root),
    (err) => err && err.code === 'INTEGRITY_DRIFT'
  );

  approveBaseline(root);
  assert.doesNotThrow(() => verifyIntegrity(root));
  console.log('PASS integrity drift fails closed and explicit approval recovers');
}

function testIdentityOverrideDenied() {
  assert.throws(
    () => assertNoRuntimeIdentityOverride({ persona_override: 'inject' }),
    (err) => err && err.code === 'INTEGRITY_IDENTITY_OVERRIDE'
  );
  assert.doesNotThrow(() => assertNoRuntimeIdentityOverride({}));
  console.log('PASS runtime identity override metadata is denied');
}

function testGuardHookEnforcesBaseline() {
  const root = mkRepoFixture();
  approveBaseline(root);

  const guard = createIntegrityGuard({ repoRoot: root, env: { OPENCLAW_INTEGRITY_GUARD: '1' } });
  assert.doesNotThrow(() => guard.enforceRequest({ metadata: {} }));

  const root2 = mkRepoFixture();
  const guardMissing = createIntegrityGuard({ repoRoot: root2, env: { OPENCLAW_INTEGRITY_GUARD: '1' } });
  assert.throws(
    () => guardMissing.enforceRequest({ metadata: {} }),
    (err) => err && err.code === 'INTEGRITY_BASELINE_MISSING'
  );
  console.log('PASS integrity guard hook enforces baseline presence');
}

function main() {
  testDeterministicBaseline();
  testDriftFailClosedAndApproval();
  testIdentityOverrideDenied();
  testGuardHookEnforcesBaseline();
}

main();
