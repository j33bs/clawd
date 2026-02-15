#!/usr/bin/env node
'use strict';

/**
 * OpenClaw plugin: expose System-2 secrets bridge via `openclaw secrets ...`.
 *
 * Why a plugin:
 * - The globally-installed `openclaw` CLI on System-2 may not ship a built-in
 *   `secrets` subcommand.
 * - OpenClaw supports dynamically-registered CLI commands via plugins.
 *
 * Safety:
 * - Delegates to this repo's `scripts/openclaw_secrets_cli.js`, which is
 *   secret-safe (no values printed).
 */

const path = require('node:path');
const { spawnSync } = require('node:child_process');

function tryRequireOpenClawSdk() {
  try {
    // Optional in unit tests; required when loaded by OpenClaw.
    // eslint-disable-next-line global-require
    return require('openclaw/plugin-sdk');
  } catch {
    return {};
  }
}

function resolveRepoRoot() {
  // This file lives in <repo>/scripts/...
  return path.resolve(__dirname, '..');
}

function shouldAutoInjectSecrets(argv) {
  const args = Array.isArray(argv) ? argv : process.argv;
  // Node: [node, openclaw.mjs, ...]
  const sub = String(args[2] || '').trim();
  return (
    sub === 'agent' ||
    sub === 'gateway' ||
    sub === 'daemon' ||
    sub === 'dashboard'
  );
}

function autoInjectSecretsForRuntime() {
  if (process.env.OPENCLAW_SYSTEM2_SECRETS_AUTO_INJECT === '0') return;
  if (process.env.ENABLE_SECRETS_BRIDGE !== '1') return;
  if (!shouldAutoInjectSecrets(process.argv)) return;

  try {
    const repoRoot = resolveRepoRoot();
    // Resolve via repo root so plugin works even when cwd is elsewhere.
    // eslint-disable-next-line global-require, import/no-dynamic-require
    const { SecretsBridge } = require(path.join(repoRoot, 'core', 'system2', 'inference', 'secrets_bridge.js'));
    const bridge = new SecretsBridge({ env: process.env });
    // Intentionally mutates process.env for this OpenClaw process so provider
    // selection can see keys without requiring `openclaw secrets exec`.
    bridge.injectRuntimeEnv(process.env);

    // Local providers shouldn't require credentials, but some OpenClaw runtime
    // paths treat "missing api key" as a hard failure. Provide a harmless
    // sentinel so local Ollama can remain a viable fallback.
    if (!process.env.OLLAMA_API_KEY) process.env.OLLAMA_API_KEY = 'ollama';
  } catch {
    // Fail-closed: never block agent startup if secrets injection fails.
  }
}

function runSecretsCli(args) {
  const repoRoot = resolveRepoRoot();
  const cliPath = path.join(repoRoot, 'scripts', 'openclaw_secrets_cli.js');
  const res = spawnSync(process.execPath, [cliPath, ...args], {
    stdio: 'inherit',
    env: {
      ...process.env,
      OPENCLAW_ROOT: process.env.OPENCLAW_ROOT || repoRoot
    }
  });
  if (typeof res.status === 'number' && res.status !== 0) {
    const err = new Error(`secrets cli exited ${res.status}`);
    err.code = res.status;
    throw err;
  }
}

const { emptyPluginConfigSchema } = tryRequireOpenClawSdk();

const plugin = {
  id: 'openclaw_secrets_plugin',
  name: 'Secrets CLI (System-2)',
  description: 'Expose the System-2 secrets bridge as `openclaw secrets ...`.',
  kind: 'tooling',
  configSchema: typeof emptyPluginConfigSchema === 'function' ? emptyPluginConfigSchema() : undefined,
  register(api) {
    if (!api || typeof api.registerCli !== 'function') {
      throw new Error('plugin api missing registerCli');
    }

    // Best-effort: make runtime commands (agent/gateway) see injected env keys
    // when ENABLE_SECRETS_BRIDGE=1, without requiring `openclaw secrets exec`.
    autoInjectSecretsForRuntime();

    api.registerCli(
      ({ program }) => {
        const secrets = program.command('secrets').description('Secrets bridge helpers (System-2).');

        secrets
          .command('status')
          .description('Show configured providers and whether secrets are present (no values).')
          .action(() => runSecretsCli(['status']));

        secrets
          .command('set')
          .description('Store a provider API key in the configured backend (prompts hidden).')
          .argument('<provider>', 'Provider id (e.g., groq, qwen, gemini, openrouter, vllm)')
          .action((provider) => runSecretsCli(['set', String(provider)]));

        secrets
          .command('unset')
          .description('Remove a provider API key from the configured backend.')
          .argument('<provider>', 'Provider id (e.g., groq, qwen, gemini, openrouter, vllm)')
          .action((provider) => runSecretsCli(['unset', String(provider)]));

        secrets
          .command('test')
          .description('Probe a provider using stored/env secrets (no values).')
          .argument('<provider>', 'Provider id (e.g., groq, qwen, gemini, openrouter, vllm)')
          .action((provider) => runSecretsCli(['test', String(provider)]));

        secrets
          .command('exec')
          .description('Run a command with secrets injected into the child env (no values).')
          .argument('<cmd...>', 'Command to run (use -- to separate openclaw args if needed)')
          .action((cmd) => runSecretsCli(['exec', '--', ...cmd.map(String)]));
      },
      { commands: ['secrets'] }
    );
  }
};

module.exports = plugin;
module.exports.default = plugin;
module.exports._test = {
  shouldAutoInjectSecrets
};
