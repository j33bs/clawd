#!/usr/bin/env node

const fs = require('fs');
const os = require('os');
const path = require('path');
const { execSync } = require('child_process');

const BASE_URL = 'https://api.telegram.org';
const DEFAULT_TIMEOUT_MS = 10000;

function parseArgs(argv) {
  const args = {
    configPath: process.env.OPENCLAW_CONFIG_PATH || path.join(os.homedir(), '.openclaw', 'openclaw.json'),
    timeoutMs: DEFAULT_TIMEOUT_MS,
    resetWebhook: false,
    dropPending: false
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--config' && argv[index + 1]) {
      args.configPath = argv[index + 1];
      index += 1;
      continue;
    }
    if (arg === '--timeout-ms' && argv[index + 1]) {
      const value = Number(argv[index + 1]);
      if (Number.isFinite(value) && value > 0) args.timeoutMs = value;
      index += 1;
      continue;
    }
    if (arg === '--reset-webhook') {
      args.resetWebhook = true;
      continue;
    }
    if (arg === '--drop-pending' || arg === '--drop-pending-updates') {
      args.dropPending = true;
      continue;
    }
  }

  return args;
}

function loadConfigToken(configPath) {
  if (!fs.existsSync(configPath)) {
    return { token: null, configReadOk: false, configError: `missing config: ${configPath}` };
  }
  try {
    const raw = fs.readFileSync(configPath, 'utf8');
    const config = JSON.parse(raw);
    const token = config && config.channels && config.channels.telegram ? config.channels.telegram.botToken : null;
    return {
      token: typeof token === 'string' ? token : null,
      configReadOk: true,
      configError: null,
      telegramMode: {
        enabled: config?.channels?.telegram?.enabled === true,
        streamMode: typeof config?.channels?.telegram?.streamMode === 'string' ? config.channels.telegram.streamMode : 'unknown',
        pollingExpected: config?.channels?.telegram?.streamMode === 'off'
      }
    };
  } catch (error) {
    return { token: null, configReadOk: false, configError: `${error.name}: ${error.message}` };
  }
}

function inspectToken(token) {
  if (typeof token !== 'string') {
    return {
      token_present: false,
      token_length: 0,
      has_whitespace: false,
      has_quotes: false,
      has_newline: false
    };
  }

  return {
    token_present: token.length > 0,
    token_length: token.length,
    has_whitespace: /\s/.test(token),
    has_quotes: /['"]/.test(token),
    has_newline: /[\r\n]/.test(token)
  };
}

function readLaunchAgentSummary() {
  if (process.platform !== 'darwin') {
    return {
      launch_agent_detected: false,
      launch_agent_has_token_env_key: false,
      launchctl_getenv_present: false,
      launchctl_getenv_length: 0
    };
  }

  const plistPath = path.join(os.homedir(), 'Library', 'LaunchAgents', 'ai.openclaw.gateway.plist');
  let hasTokenEnvKey = false;
  if (fs.existsSync(plistPath)) {
    const text = fs.readFileSync(plistPath, 'utf8');
    hasTokenEnvKey = text.includes('<key>TELEGRAM_BOT_TOKEN</key>');
  }

  let launchctlToken = '';
  try {
    launchctlToken = execSync('launchctl getenv TELEGRAM_BOT_TOKEN', {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore']
    }).trim();
  } catch (_error) {
    launchctlToken = '';
  }

  return {
    launch_agent_detected: fs.existsSync(plistPath),
    launch_agent_has_token_env_key: hasTokenEnvKey,
    launchctl_getenv_present: launchctlToken.length > 0,
    launchctl_getenv_length: launchctlToken.length
  };
}

function redactToken(text, token) {
  if (typeof text !== 'string') return '';
  if (!token || typeof token !== 'string') return text.slice(0, 200);

  const escaped = token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return text.replace(new RegExp(escaped, 'g'), '[REDACTED_TOKEN]').slice(0, 200);
}

async function telegramCall(token, method, timeoutMs, body = null) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${BASE_URL}/bot${token}/${method}`, {
      method: body ? 'POST' : 'GET',
      headers: body ? { 'content-type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal
    });

    const rawBody = await response.text();
    let parsed = null;
    try {
      parsed = rawBody ? JSON.parse(rawBody) : null;
    } catch (_error) {
      parsed = null;
    }

    clearTimeout(timer);
    return {
      http_status: response.status,
      ok: parsed && parsed.ok === true,
      body_preview: redactToken(rawBody, token),
      parsed
    };
  } catch (error) {
    clearTimeout(timer);
    return {
      http_status: 'ERROR',
      ok: false,
      body_preview: redactToken(String(error.message || error), token),
      parsed: null
    };
  }
}

function webhookSet(result) {
  if (!result || !result.parsed || !result.parsed.result) return null;
  const url = result.parsed.result.url;
  return typeof url === 'string' ? url.length > 0 : null;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const cfg = loadConfigToken(args.configPath);
  const envToken = process.env.TELEGRAM_BOT_TOKEN;
  const token = typeof envToken === 'string' && envToken.length > 0 ? envToken : cfg.token;
  const tokenSource = typeof envToken === 'string' && envToken.length > 0 ? 'env' : 'config';

  const summary = {
    token_source: tokenSource,
    config_path_checked: args.configPath,
    config_read_ok: cfg.configReadOk,
    config_error: cfg.configError || null,
    telegram_mode: cfg.telegramMode || null,
    service_env: readLaunchAgentSummary(),
    ...inspectToken(token)
  };
  console.log(JSON.stringify(summary, null, 2));

  if (!summary.token_present) {
    console.error('DIAG_FAIL: token missing');
    process.exit(2);
  }

  const getMe = await telegramCall(token, 'getMe', args.timeoutMs);
  delete getMe.parsed;
  console.log(JSON.stringify({ getMe }, null, 2));

  const getWebhookInfo = await telegramCall(token, 'getWebhookInfo', args.timeoutMs);
  const isWebhookSet = webhookSet(getWebhookInfo);
  delete getWebhookInfo.parsed;
  console.log(JSON.stringify({ getWebhookInfo, webhook_url_set: isWebhookSet }, null, 2));

  if (args.resetWebhook) {
    const deleteWebhook = await telegramCall(
      token,
      'deleteWebhook',
      args.timeoutMs,
      { drop_pending_updates: args.dropPending === true }
    );
    delete deleteWebhook.parsed;
    console.log(JSON.stringify({ deleteWebhook, drop_pending_updates: args.dropPending === true }, null, 2));
  }

  if (getMe.ok !== true) {
    process.exit(3);
  }
}

main().catch((error) => {
  console.error(`DIAG_FAIL: ${String(error && error.message ? error.message : error).slice(0, 200)}`);
  process.exit(1);
});
