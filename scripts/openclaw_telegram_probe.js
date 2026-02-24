#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

function parseArgs(argv) {
  return {
    plain: argv.includes('--plain'),
  };
}

function defaultConfigPath(env = process.env) {
  if (env.OPENCLAW_CONFIG_PATH) return env.OPENCLAW_CONFIG_PATH;
  return path.join(os.homedir(), '.openclaw', 'openclaw.json');
}

function readConfig(configPath) {
  try {
    const text = fs.readFileSync(configPath, 'utf8');
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function findTokenInObject(value) {
  if (!value || typeof value !== 'object') return null;
  if (typeof value.token === 'string' && value.token.trim()) return value.token.trim();
  if (typeof value.botToken === 'string' && value.botToken.trim()) return value.botToken.trim();
  for (const v of Object.values(value)) {
    const token = findTokenInObject(v);
    if (token) return token;
  }
  return null;
}

function resolveTelegramToken(env = process.env, config = null) {
  if (typeof env.TELEGRAM_BOT_TOKEN === 'string' && env.TELEGRAM_BOT_TOKEN.trim()) {
    return env.TELEGRAM_BOT_TOKEN.trim();
  }
  if (!config || typeof config !== 'object') return null;
  const channels = config.channels;
  if (!channels || typeof channels !== 'object') return null;
  const telegram = channels.telegram;
  return findTokenInObject(telegram);
}

async function fetchJson(url, { timeoutMs = 8000, fetchImpl = globalThis.fetch } = {}) {
  if (typeof fetchImpl !== 'function') throw new Error('fetch unavailable');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetchImpl(url, { signal: controller.signal });
    const body = await res.json().catch(() => ({}));
    return { status: res.status, body };
  } finally {
    clearTimeout(timer);
  }
}

async function buildTelegramProbe({
  env = process.env,
  configPath = defaultConfigPath(env),
  fetchImpl = globalThis.fetch,
} = {}) {
  const config = readConfig(configPath);
  const token = resolveTelegramToken(env, config);
  const base = {
    ok: false,
    mode: 'unknown',
    bot_username: null,
    webhook_url: null,
    last_error_date: null,
    last_error_message: null,
    pending_update_count: null,
    config_path: configPath,
  };
  if (!token) {
    return { ...base, error_code: 'telegram_token_missing' };
  }

  const apiBase = `https://api.telegram.org/bot${token}`;
  const [me, webhook] = await Promise.all([
    fetchJson(`${apiBase}/getMe`, { fetchImpl }),
    fetchJson(`${apiBase}/getWebhookInfo`, { fetchImpl }),
  ]);

  const meOk = !!me.body?.ok;
  const webhookInfo = webhook.body?.result || {};
  const webhookUrl = typeof webhookInfo.url === 'string' ? webhookInfo.url : '';
  return {
    ...base,
    ok: meOk,
    bot_username: me.body?.result?.username || null,
    mode: webhookUrl ? 'webhook' : 'polling',
    webhook_url: webhookUrl || null,
    last_error_date: webhookInfo.last_error_date || null,
    last_error_message: webhookInfo.last_error_message || null,
    pending_update_count: Number.isFinite(webhookInfo.pending_update_count) ? webhookInfo.pending_update_count : null,
    error_code: meOk ? null : 'telegram_probe_failed',
  };
}

function toPlain(result) {
  return [
    `ok: ${result.ok}`,
    `mode: ${result.mode}`,
    `bot_username: ${result.bot_username ?? 'null'}`,
    `webhook_url: ${result.webhook_url ?? 'null'}`,
    `pending_update_count: ${result.pending_update_count ?? 'null'}`,
    `last_error_date: ${result.last_error_date ?? 'null'}`,
    `last_error_message: ${result.last_error_message ?? 'null'}`,
    `error_code: ${result.error_code ?? 'null'}`,
    `config_path: ${result.config_path ?? 'null'}`
  ].join('\n');
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const probe = await buildTelegramProbe();
  if (args.plain) console.log(toPlain(probe));
  else console.log(JSON.stringify(probe, null, 2));
  process.exitCode = probe.ok ? 0 : 1;
}

if (require.main === module) {
  main().catch((error) => {
    const out = {
      ok: false,
      error_code: 'telegram_probe_runtime_error',
      error: String(error && error.message ? error.message : error),
    };
    console.log(JSON.stringify(out, null, 2));
    process.exitCode = 1;
  });
}

module.exports = {
  parseArgs,
  defaultConfigPath,
  resolveTelegramToken,
  buildTelegramProbe,
  toPlain,
};
