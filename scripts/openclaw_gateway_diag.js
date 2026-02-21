#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const ROUTING_ALLOWLIST_KEYS = [
  'OPENCLAW_PROVIDER_ALLOWLIST',
  'OPENCLAW_ALLOWED_PROVIDERS',
  'OPENCLAW_ALLOWLIST_PROVIDERS',
  'FREECOMPUTE_PROVIDER_ALLOWLIST',
];

const ROUTING_DEFAULT_PROVIDER_KEYS = [
  'OPENCLAW_DEFAULT_PROVIDER',
  'FREECOMPUTE_DEFAULT_PROVIDER',
];

const ROUTING_DEFAULT_MODEL_KEYS = [
  'OPENCLAW_DEFAULT_MODEL',
  'OPENCLAW_MODEL',
];

const GUARD_KEYS = [
  'OPENCLAW_STRICT_TOOL_PAYLOAD',
  'OPENCLAW_TRACE_VLLM_OUTBOUND',
  'OPENCLAW_VLLM_TOKEN_GUARD',
  'OPENCLAW_VLLM_TOKEN_GUARD_MODE',
  'OPENCLAW_VLLM_CONTEXT_MAX_TOKENS',
];

function boolFromEnv(value) {
  const normalized = String(value || '').trim().toLowerCase();
  return normalized === '1' || normalized === 'true' || normalized === 'yes' || normalized === 'on';
}

function findRepoRoot(startPath) {
  let current = path.resolve(startPath || process.cwd());
  for (let i = 0; i < 12; i += 1) {
    const gitPath = path.join(current, '.git');
    if (fs.existsSync(gitPath)) {
      return current;
    }
    const parent = path.dirname(current);
    if (parent === current) break;
    current = parent;
  }
  return null;
}

function readGitSha(repoRoot) {
  if (!repoRoot) return 'unknown';
  const gitPath = path.join(repoRoot, '.git');
  try {
    const stat = fs.statSync(gitPath);
    if (stat.isFile()) {
      const pointer = fs.readFileSync(gitPath, 'utf8').trim();
      const match = /^gitdir:\s*(.+)$/i.exec(pointer);
      if (!match) return 'unknown';
      const worktreeGitDir = path.resolve(repoRoot, match[1].trim());
      return readGitShaFromDir(worktreeGitDir);
    }
    return readGitShaFromDir(gitPath);
  } catch {
    return 'unknown';
  }
}

function readGitShaFromDir(gitDir) {
  try {
    const headPath = path.join(gitDir, 'HEAD');
    const rawHead = fs.readFileSync(headPath, 'utf8').trim();
    if (!rawHead) return 'unknown';
    if (!rawHead.startsWith('ref:')) {
      return rawHead.slice(0, 12);
    }
    const ref = rawHead.slice(5).trim();
    const refPath = path.join(gitDir, ref);
    if (fs.existsSync(refPath)) {
      return fs.readFileSync(refPath, 'utf8').trim().slice(0, 12) || 'unknown';
    }
    const packedRefs = path.join(gitDir, 'packed-refs');
    if (!fs.existsSync(packedRefs)) return 'unknown';
    const lines = fs.readFileSync(packedRefs, 'utf8').split(/\r?\n/);
    for (const line of lines) {
      if (!line || line.startsWith('#') || line.startsWith('^')) continue;
      const parts = line.trim().split(/\s+/);
      if (parts.length >= 2 && parts[1] === ref) {
        return parts[0].slice(0, 12);
      }
    }
    return 'unknown';
  } catch {
    return 'unknown';
  }
}

function firstEnv(keys, env) {
  for (const key of keys) {
    if (Object.prototype.hasOwnProperty.call(env, key) && String(env[key]).trim() !== '') {
      return { key, value: String(env[key]) };
    }
  }
  return { key: null, value: null };
}

function splitCsv(value) {
  if (!value) return [];
  return String(value)
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean);
}

function pathIfExists(candidate) {
  if (!candidate) return null;
  const full = path.resolve(candidate);
  return fs.existsSync(full) ? full : null;
}

function resolveKeyModules(repoRoot) {
  const modules = {
    policy_router_python: pathIfExists(path.join(repoRoot || '.', 'workspace', 'scripts', 'policy_router.py')),
    tool_payload_sanitizer_python: pathIfExists(path.join(repoRoot || '.', 'workspace', 'scripts', 'tool_payload_sanitizer.py')),
    tool_payload_sanitizer_node: pathIfExists(path.join(repoRoot || '.', 'core', 'system2', 'inference', 'tool_payload_sanitizer.js')),
    openai_completions_provider_gate: pathIfExists(path.join(repoRoot || '.', 'core', 'system2', 'inference', 'openai_completions_local_vllm_gate.js')),
  };
  return modules;
}

function getPythonVersion() {
  const out = spawnSync('python3', ['-V'], { encoding: 'utf8' });
  if (out.status !== 0) return null;
  return (out.stdout || out.stderr || '').trim() || null;
}

function makeGuardSnapshot(env) {
  const out = {};
  for (const key of GUARD_KEYS) {
    const present = Object.prototype.hasOwnProperty.call(env, key) && String(env[key]).trim() !== '';
    out[key] = {
      present,
      value: present ? String(env[key]) : null,
    };
  }
  return out;
}

function detectCurrentSelection(env) {
  const provider = firstEnv(['OPENCLAW_SELECTED_PROVIDER', 'OPENCLAW_PROVIDER', ...ROUTING_DEFAULT_PROVIDER_KEYS], env);
  const model = firstEnv(['OPENCLAW_SELECTED_MODEL', 'OPENCLAW_MODEL', ...ROUTING_DEFAULT_MODEL_KEYS], env);
  if (!provider.value && !model.value) {
    return null;
  }
  return {
    provider: provider.value,
    provider_source: provider.key,
    model: model.value,
    model_source: model.key,
  };
}

function buildSnapshot({ env = process.env, argv = process.argv, cwd = process.cwd() } = {}) {
  const repoRoot = findRepoRoot(cwd) || findRepoRoot(__dirname) || null;
  const allowlist = firstEnv(ROUTING_ALLOWLIST_KEYS, env);
  const defaultProvider = firstEnv(ROUTING_DEFAULT_PROVIDER_KEYS, env);
  const crossFamily = firstEnv(['OPENCLAW_ALLOW_CROSSFAMILY_FALLBACK'], env);

  return {
    routing: {
      provider_allowlist: {
        source: allowlist.key,
        value: allowlist.value,
        parsed: splitCsv(allowlist.value),
      },
      default_provider: {
        source: defaultProvider.key,
        value: defaultProvider.value,
      },
      cross_family_fallback: {
        source: crossFamily.key,
        value: crossFamily.value,
        enabled: boolFromEnv(crossFamily.value),
      },
      current_selection: detectCurrentSelection(env),
    },
    guards: makeGuardSnapshot(env),
    runtime: {
      pid: process.pid,
      ppid: process.ppid,
      cwd,
      entrypoint_module_path: argv[1] ? path.resolve(argv[1]) : null,
      runner_module_path: path.resolve(__filename),
      repo_root: repoRoot,
      key_modules: resolveKeyModules(repoRoot),
      git_sha: readGitSha(repoRoot),
      env_presence: (() => {
        const out = {};
        const keys = new Set([...ROUTING_ALLOWLIST_KEYS, ...ROUTING_DEFAULT_PROVIDER_KEYS, 'OPENCLAW_ALLOW_CROSSFAMILY_FALLBACK', ...GUARD_KEYS]);
        for (const key of keys) {
          const present = Object.prototype.hasOwnProperty.call(env, key) && String(env[key]).trim() !== '';
          out[key] = { present, value: present ? String(env[key]) : null };
        }
        return out;
      })(),
      host: {
        hostname: os.hostname(),
        platform: process.platform,
        arch: process.arch,
      },
    },
    versions: {
      node: process.version,
      python: getPythonVersion(),
    },
  };
}

function toPlain(snapshot) {
  const lines = [];
  lines.push('ROUTING');
  lines.push(`allowlist.source: ${snapshot.routing.provider_allowlist.source || 'null'}`);
  lines.push(`allowlist.value: ${snapshot.routing.provider_allowlist.value || 'null'}`);
  lines.push(`default_provider.source: ${snapshot.routing.default_provider.source || 'null'}`);
  lines.push(`default_provider.value: ${snapshot.routing.default_provider.value || 'null'}`);
  lines.push(`cross_family_fallback.enabled: ${snapshot.routing.cross_family_fallback.enabled}`);
  lines.push(`cross_family_fallback.value: ${snapshot.routing.cross_family_fallback.value || 'null'}`);
  lines.push(`current_selection.provider: ${snapshot.routing.current_selection && snapshot.routing.current_selection.provider ? snapshot.routing.current_selection.provider : 'null'}`);
  lines.push(`current_selection.model: ${snapshot.routing.current_selection && snapshot.routing.current_selection.model ? snapshot.routing.current_selection.model : 'null'}`);

  lines.push('');
  lines.push('GUARDS');
  for (const [key, info] of Object.entries(snapshot.guards)) {
    lines.push(`${key}: present=${info.present} value=${info.value == null ? 'null' : info.value}`);
  }

  lines.push('');
  lines.push('RUNTIME');
  lines.push(`pid: ${snapshot.runtime.pid}`);
  lines.push(`cwd: ${snapshot.runtime.cwd}`);
  lines.push(`entrypoint_module_path: ${snapshot.runtime.entrypoint_module_path || 'null'}`);
  lines.push(`runner_module_path: ${snapshot.runtime.runner_module_path}`);
  lines.push(`repo_root: ${snapshot.runtime.repo_root || 'null'}`);
  lines.push(`git_sha: ${snapshot.runtime.git_sha}`);
  for (const [key, modulePath] of Object.entries(snapshot.runtime.key_modules)) {
    lines.push(`${key}: ${modulePath || 'null'}`);
  }

  lines.push('');
  lines.push('VERSIONS');
  lines.push(`node: ${snapshot.versions.node}`);
  lines.push(`python: ${snapshot.versions.python || 'null'}`);

  return lines.join('\n');
}

function parseArgs(argv) {
  return {
    plain: argv.includes('--plain'),
  };
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  const snapshot = buildSnapshot();
  if (opts.plain) {
    process.stdout.write(`${toPlain(snapshot)}\n`);
    return;
  }
  process.stdout.write(`${JSON.stringify(snapshot, null, 2)}\n`);
}

if (require.main === module) {
  main();
}

module.exports = {
  buildSnapshot,
  toPlain,
  parseArgs,
  boolFromEnv,
};
