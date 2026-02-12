#!/usr/bin/env node
'use strict';

const { spawnSync } = require('node:child_process');

const { HELP_LINES: SECRETS_HELP_LINES, run: runSecretsCli } = require('./openclaw_secrets_cli');
const { SecretsBridge } = require('../core/system2/inference/secrets_bridge');

const BRIDGE_INJECTION_COMMANDS = new Set(['dashboard', 'start', 'gateway']);

function writeHelp(stream) {
  stream.write('Usage: openclaw <command> [args]\n');
  stream.write('\n');
  stream.write('Commands:\n');
  for (const line of SECRETS_HELP_LINES) {
    stream.write(`${line}\n`);
  }
}

function launchPassthrough(args, options = {}) {
  const stderr = options.stderr || process.stderr;
  const env = options.env || process.env;
  const childEnv = { ...env };
  const command = args[0] || '';

  if (BRIDGE_INJECTION_COMMANDS.has(command) && childEnv.ENABLE_SECRETS_BRIDGE === '1') {
    try {
      const bridge = new SecretsBridge({ env: childEnv });
      bridge.injectRuntimeEnv(childEnv);
    } catch (error) {
      stderr.write(`openclaw: secrets bridge injection skipped: ${error.message}\n`);
    }
  }

  const passthroughCmd = childEnv.OPENCLAW_CLI_PASSTHROUGH_BIN || 'openclaw';
  const alreadyForwarding = childEnv.OPENCLAW_CLI_FORWARDING === '1';
  if (alreadyForwarding && passthroughCmd === 'openclaw') {
    stderr.write('openclaw: passthrough recursion detected; set OPENCLAW_CLI_PASSTHROUGH_BIN to your upstream binary.\n');
    return 1;
  }

  childEnv.OPENCLAW_CLI_FORWARDING = '1';
  const run = spawnSync(passthroughCmd, args, {
    stdio: 'inherit',
    env: childEnv
  });

  if (run.error) {
    stderr.write(`openclaw: failed to launch upstream command: ${run.error.message}\n`);
    return 1;
  }

  return typeof run.status === 'number' ? run.status : 1;
}

async function run(argv, options = {}) {
  const stdout = options.stdout || process.stdout;
  const stderr = options.stderr || process.stderr;
  const env = options.env || process.env;
  const args = Array.isArray(argv) ? argv : [];
  const command = args[0];

  if (!command || command === '--help' || command === '-h' || command === 'help') {
    writeHelp(stdout);
    return 0;
  }

  if (command === 'secrets') {
    const secretsArgs = args.slice(1);
    if (secretsArgs.length === 0) {
      secretsArgs.push('--help');
    }
    return runSecretsCli(secretsArgs, { stdout, stderr, env });
  }

  return launchPassthrough(args, { stderr, env });
}

if (require.main === module) {
  run(process.argv.slice(2))
    .then((code) => {
      process.exit(typeof code === 'number' ? code : 0);
    })
    .catch((error) => {
      console.error(`openclaw command failed: ${error.message}`);
      process.exit(1);
    });
}

module.exports = {
  BRIDGE_INJECTION_COMMANDS,
  launchPassthrough,
  run,
  writeHelp
};
