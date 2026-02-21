'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');

const INLINE_MAX_BYTES = 32 * 1024;

function toPayloadString(payload) {
  if (payload == null) return '';
  if (typeof payload === 'string') return payload;
  return JSON.stringify(payload);
}

function buildSafeSpawnPlan(cmd, args = [], options = {}, payload, transportArg = '--payload-file') {
  const payloadText = toPayloadString(payload);
  const payloadBytes = Buffer.byteLength(payloadText || '', 'utf8');
  const baseArgs = Array.isArray(args) ? args.slice() : [];
  const baseEnv = { ...(options.env || process.env) };

  if (!payloadText) {
    return {
      cmd,
      args: baseArgs,
      options: { ...options, env: baseEnv },
      mode: 'none',
      payloadBytes,
      payloadText: null,
      payloadFile: null,
    };
  }

  if (payloadBytes <= INLINE_MAX_BYTES) {
    return {
      cmd,
      args: baseArgs,
      options: { ...options, env: baseEnv },
      mode: 'stdin',
      payloadBytes,
      payloadText,
      payloadFile: null,
    };
  }

  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'openclaw-payload-'));
  const payloadFile = path.join(dir, 'payload.json');
  fs.writeFileSync(payloadFile, `${payloadText}\n`, { encoding: 'utf8', mode: 0o600 });

  return {
    cmd,
    args: [...baseArgs, transportArg, payloadFile],
    options: { ...options, env: baseEnv },
    mode: 'file',
    payloadBytes,
    payloadText: null,
    payloadFile,
  };
}

function safeSpawn(cmd, args = [], options = {}, payload, transportArg = '--payload-file') {
  const plan = buildSafeSpawnPlan(cmd, args, options, payload, transportArg);
  const child = spawn(plan.cmd, plan.args, plan.options);

  if (plan.mode === 'stdin' && child.stdin) {
    child.stdin.write(plan.payloadText);
    child.stdin.end();
  }

  return { child, plan };
}

module.exports = {
  INLINE_MAX_BYTES,
  buildSafeSpawnPlan,
  safeSpawn,
};
