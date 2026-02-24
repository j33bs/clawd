#!/usr/bin/env node
'use strict';

const readline = require('node:readline/promises');
const { spawnSync } = require('node:child_process');

const { SecretsBridge } = require('../core/system2/inference/secrets_bridge');

function usage() {
  console.error('Usage: node scripts/openclaw_secrets_cli.js <set|unset|status|test|exec> [provider|-- <cmd...>]');
  process.exit(2);
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

function hasConfiguredFilePassphrase() {
  return Boolean(process.env.SECRETS_FILE_PASSPHRASE || process.env.SECRETS_FILE_PASSPHRASE_FILE);
}

async function main() {
  const args = process.argv.slice(2);
  const command = args[0];
  const provider = args[1];

  if (!command || !['set', 'unset', 'status', 'test', 'exec'].includes(command)) {
    usage();
  }

  const bridge = new SecretsBridge();

  if (command === 'status') {
    const rows = bridge.status();
    // Safe status header: booleans/labels only, never secret values.
    console.log(`secrets_bridge_enabled=${bridge.config.enabled ? 'true' : 'false'}`);
    // Rows already include the detected backend, but printing it once makes "status" actionable.
    console.log(`secrets_backend=${rows[0]?.backend || 'unknown'}`);
    for (const row of rows) {
      const state = row.present ? 'present' : 'missing';
      const envState = row.injectedFromEnv ? 'env_override' : 'store_only';
      console.log(`${row.provider}: ${state} (${envState}) [${row.envVar}]`);
    }
    return;
  }

  if (!provider) {
    usage();
  }

  if (command === 'set') {
    const secret = await promptHidden(`Enter API key for ${provider}: `);
    if (!secret) {
      throw new Error('empty secret');
    }

    let passphrase = null;
    if ((process.env.SECRETS_BACKEND || '').toLowerCase() === 'file' && !hasConfiguredFilePassphrase()) {
      passphrase = await promptHidden('Enter passphrase for file backend: ');
    }

    const saved = bridge.setSecret(provider, secret, { passphrase });
    // Never print secret values or partial secret tails. Keep output to names only.
    console.log(`stored: provider=${saved.provider} backend=${saved.backend} envVar=${saved.envVar}`);
    return;
  }

  if (command === 'unset') {
    let passphrase = null;
    if ((process.env.SECRETS_BACKEND || '').toLowerCase() === 'file' && !hasConfiguredFilePassphrase()) {
      passphrase = await promptHidden('Enter passphrase for file backend: ');
    }
    const removed = bridge.unsetSecret(provider, { passphrase });
    console.log(`removed: provider=${removed.provider} backend=${removed.backend} removed=${removed.removed}`);
    return;
  }

  if (command === 'test') {
    let passphrase = null;
    if ((process.env.SECRETS_BACKEND || '').toLowerCase() === 'file' && !hasConfiguredFilePassphrase()) {
      passphrase = await promptLine('Passphrase for file backend (input visible): ');
    }
    const probe = await bridge.testProvider(provider, { passphrase });
    console.log(`probe: provider=${probe.provider} ok=${probe.ok} code=${probe.code}`);
    return;
  }

  if (command === 'exec') {
    // Run a command with secrets injected into the child environment.
    // This is an operator convenience to support workflows like:
    //   ENABLE_SECRETS_BRIDGE=1 openclaw secrets exec -- openclaw agent --local ...
    //
    // Safety:
    // - Never prints secret values.
    // - Reports injected ENV KEY NAMES only.
    if (!bridge.config.enabled) {
      throw new Error('secrets bridge disabled (set ENABLE_SECRETS_BRIDGE=1)');
    }

    let cmdArgs = args.slice(1);
    if (cmdArgs[0] === '--') {
      cmdArgs = cmdArgs.slice(1);
    }
    if (cmdArgs.length === 0) {
      usage();
    }

    const childEnv = { ...process.env };
    const injection = bridge.injectRuntimeEnv(childEnv);
    const injectedKeys = Array.from(new Set((injection.injected || []).map((e) => e.envVar))).sort();

    if (injectedKeys.length > 0) {
      console.log(`secrets_bridge_injected_env_keys=${injectedKeys.join(',')}`);
    } else {
      console.log('secrets_bridge_injected_env_keys=(none)');
    }

    const res = spawnSync(cmdArgs[0], cmdArgs.slice(1), {
      env: childEnv,
      stdio: 'inherit'
    });

    const status = typeof res.status === 'number' ? res.status : 1;
    process.exit(status);
  }
}

main().catch((error) => {
  console.error(`secrets command failed: ${error.message}`);
  process.exit(1);
});
