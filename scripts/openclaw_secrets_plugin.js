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
      },
      { commands: ['secrets'] }
    );
  }
};

module.exports = plugin;
module.exports.default = plugin;
