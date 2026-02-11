'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const { loadConfig } = require('../../sys/config');

function resolvePath(root, maybeRelativePath) {
  const target = String(maybeRelativePath || '').trim();
  if (!target) {
    return path.resolve(root);
  }
  if (path.isAbsolute(target)) {
    return path.resolve(target);
  }
  return path.resolve(root, target);
}

function sha256FileHex(filePath) {
  const data = fs.readFileSync(filePath);
  return crypto.createHash('sha256').update(data).digest('hex');
}

function semverLike(value) {
  return /^\d+\.\d+\.\d+$/.test(String(value || '').trim());
}

function probeStartupInvariants(options = {}) {
  const workspaceRoot = options.workspaceRoot || process.cwd();
  const config = options.config || loadConfig();
  const system2 = config && config.system2 ? config.system2 : {};
  const checks = [];

  function addCheck(name, ok, details = {}) {
    checks.push({
      name,
      ok: Boolean(ok),
      ...details
    });
  }

  const configuredWorkspacePath = system2.workspace_path || '.';
  const resolvedWorkspacePath = resolvePath(workspaceRoot, configuredWorkspacePath);
  addCheck('workspace_exists', fs.existsSync(resolvedWorkspacePath), {
    expected: 'existing directory',
    actual: resolvedWorkspacePath
  });

  const identityPath = resolvePath(resolvedWorkspacePath, system2.identity_path || 'IDENTITY.md');
  addCheck('identity_exists', fs.existsSync(identityPath), {
    expected: 'existing file',
    actual: identityPath
  });

  addCheck('policy_version_semver', semverLike(system2.policy_version), {
    expected: 'x.y.z',
    actual: system2.policy_version || null
  });

  const allowlistPath = resolvePath(workspaceRoot, system2.tool_allowlist_path || '');
  if (!fs.existsSync(allowlistPath)) {
    addCheck('tool_allowlist_exists', false, {
      expected: 'existing file',
      actual: allowlistPath
    });
  } else {
    addCheck('tool_allowlist_exists', true, {
      expected: 'existing file',
      actual: allowlistPath
    });
    const actualHash = sha256FileHex(allowlistPath);
    addCheck('tool_allowlist_hash_match', actualHash === system2.tool_allowlist_hash, {
      expected: system2.tool_allowlist_hash || null,
      actual: actualHash
    });
  }

  const keyEnvName = String(system2.envelope_signing_key_env || '').trim();
  addCheck('envelope_key_env_name_valid', /^[A-Z0-9_]+$/.test(keyEnvName), {
    expected: 'UPPERCASE_UNDERSCORE_ENV_NAME',
    actual: keyEnvName || null
  });

  const ok = checks.every((check) => check.ok);

  return {
    ok,
    checked_at: new Date().toISOString(),
    checks,
    config_meta: config.__meta || null,
    resolved: {
      workspace_path: resolvedWorkspacePath,
      identity_path: identityPath,
      allowlist_path: allowlistPath
    }
  };
}

module.exports = {
  probeStartupInvariants,
  sha256FileHex,
  resolvePath
};
