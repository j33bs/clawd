#!/usr/bin/env node
'use strict';

const readline = require('node:readline/promises');

const { SecretsBridge } = require('../core/system2/inference/secrets_bridge');

function usage() {
  console.error('Usage: node scripts/openclaw_secrets_cli.js <set|unset|status|test> [provider]');
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

async function main() {
  const args = process.argv.slice(2);
  const command = args[0];
  const provider = args[1];

  if (!command || !['set', 'unset', 'status', 'test'].includes(command)) {
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
    if ((process.env.SECRETS_BACKEND || '').toLowerCase() === 'file' && !process.env.SECRETS_FILE_PASSPHRASE) {
      passphrase = await promptHidden('Enter passphrase for file backend: ');
    }

    const saved = bridge.setSecret(provider, secret, { passphrase });
    console.log(`stored: provider=${saved.provider} backend=${saved.backend} fingerprint=${saved.fingerprint}`);
    return;
  }

  if (command === 'unset') {
    let passphrase = null;
    if ((process.env.SECRETS_BACKEND || '').toLowerCase() === 'file' && !process.env.SECRETS_FILE_PASSPHRASE) {
      passphrase = await promptHidden('Enter passphrase for file backend: ');
    }
    const removed = bridge.unsetSecret(provider, { passphrase });
    console.log(`removed: provider=${removed.provider} backend=${removed.backend} removed=${removed.removed}`);
    return;
  }

  if (command === 'test') {
    let passphrase = null;
    if ((process.env.SECRETS_BACKEND || '').toLowerCase() === 'file' && !process.env.SECRETS_FILE_PASSPHRASE) {
      passphrase = await promptLine('Passphrase for file backend (input visible): ');
    }
    const probe = await bridge.testProvider(provider, { passphrase });
    console.log(`probe: provider=${probe.provider} ok=${probe.ok} code=${probe.code}`);
  }
}

main().catch((error) => {
  console.error(`secrets command failed: ${error.message}`);
  process.exit(1);
});
