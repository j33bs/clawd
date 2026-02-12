#!/usr/bin/env node
'use strict';

const readline = require('node:readline/promises');

const { SecretsBridge } = require('../core/system2/inference/secrets_bridge');

const COMMANDS = new Set(['set', 'unset', 'status', 'test']);

const HELP_LINES = [
  'secrets  Manage API keys for providers (store, test, list)',
  'set        Store a provider API key',
  'unset      Remove stored key',
  'status     Show which provider keys are configured',
  'test       Test connectivity (no key printed)'
];

function writeUsage(stream) {
  stream.write('Usage: openclaw secrets <set|unset|status|test> [provider]\n');
  stream.write('\n');
  for (const line of HELP_LINES) {
    stream.write(`${line}\n`);
  }
}

function promptLine(promptText) {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });
  return rl.question(promptText).finally(() => rl.close());
}

function promptHidden(promptText) {
  return new Promise((resolve, reject) => {
    const stdin = process.stdin;
    const stdout = process.stdout;

    if (!stdin.isTTY || !stdout.isTTY) {
      reject(new Error('hidden input requires a TTY'));
      return;
    }

    let value = '';
    stdout.write(promptText);
    stdin.setRawMode(true);
    stdin.resume();
    stdin.setEncoding('utf8');

    function cleanup() {
      stdin.setRawMode(false);
      stdin.pause();
      stdin.removeListener('data', onData);
      stdout.write('\n');
    }

    function onData(ch) {
      if (ch === '\u0003') {
        cleanup();
        reject(new Error('cancelled'));
        return;
      }
      if (ch === '\r' || ch === '\n') {
        cleanup();
        resolve(value);
        return;
      }
      if (ch === '\u0008' || ch === '\u007f') {
        value = value.slice(0, -1);
        return;
      }
      value += ch;
    }

    stdin.on('data', onData);
  });
}

async function main() {
  const args = process.argv.slice(2);
  return run(args);
}

async function run(args, options = {}) {
  const stdout = options.stdout || process.stdout;
  const stderr = options.stderr || process.stderr;
  const env = options.env || process.env;
  const bridgeFactory = options.bridgeFactory || (() => new SecretsBridge({ env }));
  const command = args[0];
  const provider = args[1];

  if (!command || command === '--help' || command === '-h' || command === 'help') {
    writeUsage(stdout);
    return 0;
  }

  if (!COMMANDS.has(command)) {
    writeUsage(stderr);
    return 2;
  }

  const bridge = bridgeFactory();

  if (!bridge.config || !bridge.config.enabled) {
    stdout.write('Secrets Bridge is disabled (ENABLE_SECRETS_BRIDGE=0). Enable it to manage provider keys.\n');
    return 0;
  }

  if (command === 'status') {
    const rows = bridge.status();
    for (const row of rows) {
      const state = row.present ? 'present' : 'missing';
      const envState = row.injectedFromEnv ? 'env_override' : 'store_only';
      const backendNote = row.backendError ? ` backend_error=${row.backendError}` : '';
      stdout.write(`${row.provider}: ${state} (${envState}) [${row.envVar}]${backendNote}\n`);
    }
    return 0;
  }

  if (!provider) {
    writeUsage(stderr);
    return 2;
  }

  if (command === 'set') {
    const secret = await promptHidden(`Enter API key for ${provider}: `);
    if (!secret) {
      throw new Error('empty secret');
    }

    let passphrase = null;
    if ((env.SECRETS_BACKEND || '').toLowerCase() === 'file' && !env.SECRETS_FILE_PASSPHRASE) {
      passphrase = await promptHidden('Enter passphrase for file backend: ');
    }

    const saved = bridge.setSecret(provider, secret, { passphrase });
    stdout.write(`stored: provider=${saved.provider} backend=${saved.backend} fingerprint=${saved.fingerprint}\n`);
    return 0;
  }

  if (command === 'unset') {
    let passphrase = null;
    if ((env.SECRETS_BACKEND || '').toLowerCase() === 'file' && !env.SECRETS_FILE_PASSPHRASE) {
      passphrase = await promptHidden('Enter passphrase for file backend: ');
    }
    const removed = bridge.unsetSecret(provider, { passphrase });
    stdout.write(`removed: provider=${removed.provider} backend=${removed.backend} removed=${removed.removed}\n`);
    return 0;
  }

  if (command === 'test') {
    let passphrase = null;
    if ((env.SECRETS_BACKEND || '').toLowerCase() === 'file' && !env.SECRETS_FILE_PASSPHRASE) {
      passphrase = await promptLine('Passphrase for file backend (input visible): ');
    }
    const probe = await bridge.testProvider(provider, { passphrase });
    stdout.write(`probe: provider=${probe.provider} ok=${probe.ok} code=${probe.code}\n`);
    return 0;
  }
}

if (require.main === module) {
  main()
    .then((code) => {
      process.exit(typeof code === 'number' ? code : 0);
    })
    .catch((error) => {
      console.error(`secrets command failed: ${error.message}`);
      process.exit(1);
    });
}

module.exports = {
  HELP_LINES,
  run
};
