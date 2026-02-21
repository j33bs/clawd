'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const DEFAULT_BASELINE_RELATIVE_PATH = 'workspace/governance/INTEGRITY_BASELINE.json';

const ROLE_ORDER = Object.freeze([
  'constitution',
  'goals',
  'identity',
  'soul',
  'user'
]);

const ROLE_CANDIDATES = Object.freeze({
  constitution: Object.freeze([
    'workspace/governance/CONSTITUTION.md',
    'workspace/CONSTITUTION.md',
    'workspace/governance/PRINCIPLES.md',
    'workspace/PRINCIPLES.md'
  ]),
  goals: Object.freeze([
    'workspace/governance/GOALS.md',
    'workspace/GOALS.md'
  ]),
  identity: Object.freeze([
    'workspace/governance/IDENTITY.md',
    'workspace/IDENTITY.md'
  ]),
  soul: Object.freeze([
    'workspace/governance/SOUL.md',
    'workspace/SOUL.md'
  ]),
  user: Object.freeze([
    'workspace/governance/USER.md',
    'workspace/USER.md'
  ])
});

const IDENTITY_OVERRIDE_KEYS = Object.freeze([
  'identity_override',
  'soul_override',
  'user_override',
  'persona_override',
  'system_prompt_override',
  'constitution_override',
  'goals_override'
]);

function integrityError(code, message, detail) {
  const err = new Error(message);
  err.name = 'IntegrityGuardError';
  err.code = code;
  if (detail) err.detail = detail;
  return err;
}

function resolveRepoRoot(startDir) {
  let current = path.resolve(startDir || process.cwd());
  for (let i = 0; i < 8; i += 1) {
    if (fs.existsSync(path.join(current, '.git'))) return current;
    const parent = path.dirname(current);
    if (parent === current) break;
    current = parent;
  }
  throw integrityError('INTEGRITY_REPO_ROOT_NOT_FOUND', 'could not resolve repo root from filesystem');
}

function resolveBaselinePath(repoRoot, opts = {}) {
  const rel = opts.baselineRelativePath || DEFAULT_BASELINE_RELATIVE_PATH;
  return {
    relative: rel,
    absolute: path.join(repoRoot, rel)
  };
}

function sha256File(absPath) {
  const digest = crypto.createHash('sha256');
  digest.update(fs.readFileSync(absPath));
  return digest.digest('hex');
}

function resolveAnchorFiles(repoRoot) {
  const resolved = [];
  for (const role of ROLE_ORDER) {
    const candidates = ROLE_CANDIDATES[role] || [];
    let found = null;
    for (const rel of candidates) {
      const abs = path.join(repoRoot, rel);
      if (fs.existsSync(abs)) {
        found = rel;
        break;
      }
    }
    if (!found) {
      throw integrityError(
        'INTEGRITY_ANCHOR_MISSING',
        `missing integrity anchor for role=${role}`,
        { role, candidates }
      );
    }
    resolved.push({ role, path: found });
  }
  return resolved;
}

function computeBaseline(repoRootInput) {
  const repoRoot = resolveRepoRoot(repoRootInput);
  const anchors = resolveAnchorFiles(repoRoot);
  const files = anchors.map((entry) => {
    const abs = path.join(repoRoot, entry.path);
    return {
      role: entry.role,
      path: entry.path,
      sha256: sha256File(abs)
    };
  });
  return {
    version: 1,
    files
  };
}

function writeBaseline(repoRootInput, baseline, opts = {}) {
  const repoRoot = resolveRepoRoot(repoRootInput);
  const baselinePath = resolveBaselinePath(repoRoot, opts);
  fs.mkdirSync(path.dirname(baselinePath.absolute), { recursive: true });
  fs.writeFileSync(
    baselinePath.absolute,
    `${JSON.stringify(baseline, null, 2)}\n`,
    'utf8'
  );
  return baselinePath;
}

function loadBaseline(repoRootInput, opts = {}) {
  const repoRoot = resolveRepoRoot(repoRootInput);
  const baselinePath = resolveBaselinePath(repoRoot, opts);
  if (!fs.existsSync(baselinePath.absolute)) {
    throw integrityError(
      'INTEGRITY_BASELINE_MISSING',
      `integrity baseline missing: ${baselinePath.relative}`,
      { baselinePath: baselinePath.relative }
    );
  }
  let parsed;
  try {
    parsed = JSON.parse(fs.readFileSync(baselinePath.absolute, 'utf8'));
  } catch (error) {
    throw integrityError(
      'INTEGRITY_BASELINE_INVALID',
      `integrity baseline invalid JSON: ${baselinePath.relative}`,
      { baselinePath: baselinePath.relative, reason: error.message }
    );
  }
  if (!parsed || parsed.version !== 1 || !Array.isArray(parsed.files)) {
    throw integrityError(
      'INTEGRITY_BASELINE_INVALID',
      `integrity baseline schema invalid: ${baselinePath.relative}`,
      { baselinePath: baselinePath.relative }
    );
  }
  return parsed;
}

function verifyIntegrity(repoRootInput, opts = {}) {
  const repoRoot = resolveRepoRoot(repoRootInput);
  const baseline = loadBaseline(repoRoot, opts);
  const actual = computeBaseline(repoRoot);

  const expectedByRole = new Map();
  for (const file of baseline.files) {
    expectedByRole.set(file.role, file);
  }

  const drift = [];
  for (const file of actual.files) {
    const expected = expectedByRole.get(file.role);
    if (!expected) {
      drift.push({
        role: file.role,
        reason: 'missing_role_in_baseline',
        actualPath: file.path
      });
      continue;
    }
    if (expected.path !== file.path || expected.sha256 !== file.sha256) {
      drift.push({
        role: file.role,
        reason: 'hash_mismatch',
        expectedPath: expected.path,
        actualPath: file.path,
        expectedSha256: expected.sha256,
        actualSha256: file.sha256
      });
    }
  }

  if (drift.length > 0) {
    throw integrityError(
      'INTEGRITY_DRIFT',
      'integrity anchor drift detected; explicit baseline approval required',
      { drift, baselinePath: opts.baselineRelativePath || DEFAULT_BASELINE_RELATIVE_PATH }
    );
  }

  return { ok: true, checked: actual.files.length };
}

function approveBaseline(repoRootInput, opts = {}) {
  const repoRoot = resolveRepoRoot(repoRootInput);
  const baseline = computeBaseline(repoRoot);
  writeBaseline(repoRoot, baseline, opts);
  return baseline;
}

function assertNoRuntimeIdentityOverride(metadata) {
  const md = metadata && typeof metadata === 'object' ? metadata : {};
  const hits = [];
  for (const key of IDENTITY_OVERRIDE_KEYS) {
    if (!Object.prototype.hasOwnProperty.call(md, key)) continue;
    const value = md[key];
    if (value === undefined || value === null || value === false || value === '') continue;
    hits.push(key);
  }
  if (hits.length > 0) {
    throw integrityError(
      'INTEGRITY_IDENTITY_OVERRIDE',
      'runtime metadata attempted identity/governance override',
      { keys: hits }
    );
  }
}

function createIntegrityGuard(opts = {}) {
  const env = opts.env || process.env;
  const enabled = String(env.OPENCLAW_INTEGRITY_GUARD || '1') !== '0';
  const repoRoot = resolveRepoRoot(opts.repoRoot || process.cwd());

  function verifyOnce() {
    if (!enabled) return { ok: true, skipped: 'disabled' };
    const result = verifyIntegrity(repoRoot, opts);
    return { ok: true, verified: true, checked: result.checked };
  }

  function enforceRequest(params) {
    verifyOnce();
    const metadata = params && typeof params === 'object' ? params.metadata : null;
    assertNoRuntimeIdentityOverride(metadata);
  }

  return {
    enabled,
    verifyOnce,
    enforceRequest
  };
}

module.exports = {
  DEFAULT_BASELINE_RELATIVE_PATH,
  ROLE_ORDER,
  ROLE_CANDIDATES,
  createIntegrityGuard,
  resolveRepoRoot,
  resolveAnchorFiles,
  computeBaseline,
  writeBaseline,
  loadBaseline,
  verifyIntegrity,
  approveBaseline,
  assertNoRuntimeIdentityOverride
};
