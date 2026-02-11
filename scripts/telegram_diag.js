#!/usr/bin/env node

const fs = require('fs');
const os = require('os');
const path = require('path');
const { execSync } = require('child_process');

const BASE_URL = 'https://api.telegram.org';
const DEFAULT_TIMEOUT_MS = 10000;
const DEFAULT_REPORT_PATH = path.join(process.cwd(), 'reports', 'diag', 'telegram_e2e.json');
const LOG_SCAN_INTERVAL_MS = 1000;

function getArgValue(argv, name, defaultValue = null) {
  const prefixed = `${name}=`;
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === name && argv[index + 1]) {
      return argv[index + 1];
    }
    if (arg.startsWith(prefixed)) {
      return arg.slice(prefixed.length);
    }
  }
  return defaultValue;
}

function hasArg(argv, name) {
  return argv.includes(name);
}

function parseArgs(argv) {
  const timeoutRaw = getArgValue(argv, '--timeout-ms', String(DEFAULT_TIMEOUT_MS));
  const timeoutMs = Number(timeoutRaw);

  return {
    configPath: getArgValue(argv, '--config', process.env.OPENCLAW_CONFIG_PATH || path.join(os.homedir(), '.openclaw', 'openclaw.json')),
    timeoutMs: Number.isFinite(timeoutMs) && timeoutMs > 0 ? timeoutMs : DEFAULT_TIMEOUT_MS,
    resetWebhook: hasArg(argv, '--reset-webhook'),
    dropPending: hasArg(argv, '--drop-pending') || hasArg(argv, '--drop-pending-updates'),
    e2e: hasArg(argv, '--e2e'),
    chatId: getArgValue(argv, '--chat-id', null),
    followOpenclawLogs: hasArg(argv, '--follow-openclaw-logs'),
    reportPath: getArgValue(argv, '--report-path', DEFAULT_REPORT_PATH)
  };
}

function loadConfigToken(configPath) {
  if (!fs.existsSync(configPath)) {
    return { token: null, configReadOk: false, configError: `missing config: ${configPath}` };
  }

  try {
    const raw = fs.readFileSync(configPath, 'utf8');
    const config = JSON.parse(raw);
    const telegram = (config && config.channels && config.channels.telegram) || {};
    const token = typeof telegram.botToken === 'string' ? telegram.botToken : null;

    return {
      token,
      configReadOk: true,
      configError: null,
      telegramMode: {
        enabled: telegram.enabled === true,
        streamMode: typeof telegram.streamMode === 'string' ? telegram.streamMode : 'unknown',
        pollingExpected: telegram.streamMode === 'off'
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

function classifyTokenError(tokenMeta) {
  if (!tokenMeta.token_present) return 'token_missing';
  if (tokenMeta.has_whitespace || tokenMeta.has_quotes || tokenMeta.has_newline) return 'token_malformed';
  return null;
}

function classifyHttpError(status) {
  if (status === 401) return 'token_rejected_401';
  if (status === 404) return 'endpoint_not_found_404';
  return null;
}

async function telegramCall(token, method, timeoutMs, body = null, query = null) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  const url = new URL(`${BASE_URL}/bot${token}/${method}`);
  if (query && typeof query === 'object') {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, String(value));
      }
    }
  }

  try {
    const response = await fetch(url.toString(), {
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
      parsed,
      error_category: classifyHttpError(response.status)
    };
  } catch (error) {
    clearTimeout(timer);
    return {
      http_status: 'ERROR',
      ok: false,
      body_preview: redactToken(String(error.message || error), token),
      parsed: null,
      error_category: 'network_error'
    };
  }
}

function webhookSet(result) {
  if (!result || !result.parsed || !result.parsed.result) return null;
  const url = result.parsed.result.url;
  return typeof url === 'string' ? url.length > 0 : null;
}

function sanitizeUpdateMeta(update) {
  const payload = update && (update.message || update.edited_message || update.channel_post || update.edited_channel_post);
  let kind = 'unknown';
  if (update && update.message) kind = 'message';
  else if (update && update.edited_message) kind = 'edited_message';
  else if (update && update.channel_post) kind = 'channel_post';
  else if (update && update.edited_channel_post) kind = 'edited_channel_post';

  return {
    update_id: typeof update?.update_id === 'number' ? update.update_id : null,
    kind,
    chat_id: typeof payload?.chat?.id === 'number' ? payload.chat.id : null,
    message_id: typeof payload?.message_id === 'number' ? payload.message_id : null,
    from_is_bot: payload?.from?.is_bot === true,
    has_text: typeof payload?.text === 'string',
    reply_to_message_id: typeof payload?.reply_to_message?.message_id === 'number' ? payload.reply_to_message.message_id : null
  };
}

function ensureDirectory(filePath) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
}

function writeJson(filePath, payload) {
  ensureDirectory(filePath);
  fs.writeFileSync(filePath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function initLogWatcher() {
  const paths = [
    path.join(os.homedir(), '.openclaw', 'logs', 'gateway.log'),
    path.join(os.homedir(), '.openclaw', 'logs', 'gateway.err.log')
  ];

  const state = paths.map((filePath) => {
    const size = fs.existsSync(filePath) ? fs.statSync(filePath).size : 0;
    return { filePath, offset: size };
  });

  return {
    poll() {
      let sawInboundPath = false;
      let sawOutboundPath = false;

      for (const entry of state) {
        if (!fs.existsSync(entry.filePath)) continue;
        const stat = fs.statSync(entry.filePath);
        if (stat.size <= entry.offset) continue;

        const readStart = stat.size - entry.offset > 131072 ? stat.size - 131072 : entry.offset;
        const length = stat.size - readStart;
        const fd = fs.openSync(entry.filePath, 'r');
        const buffer = Buffer.alloc(length);
        fs.readSync(fd, buffer, 0, length, readStart);
        fs.closeSync(fd);
        entry.offset = stat.size;

        const text = buffer.toString('utf8');
        if (/\[telegram\].*(getUpdates|update)/i.test(text)) {
          sawInboundPath = true;
        }
        if (/\[telegram\].*(sendMessage|final reply|block reply)/i.test(text)) {
          sawOutboundPath = true;
        }
      }

      return { sawInboundPath, sawOutboundPath };
    }
  };
}

async function pollUpdatesSince(token, baselineUpdateId, timeoutMs) {
  const query = {
    timeout: 1,
    limit: 20,
    allowed_updates: JSON.stringify(['message', 'edited_message', 'channel_post', 'edited_channel_post'])
  };
  if (typeof baselineUpdateId === 'number') {
    query.offset = baselineUpdateId + 1;
  }

  const result = await telegramCall(token, 'getUpdates', timeoutMs, null, query);
  const updates = Array.isArray(result.parsed?.result) ? result.parsed.result : [];
  const maxUpdateId = updates.reduce((max, item) => {
    if (typeof item?.update_id === 'number' && item.update_id > max) return item.update_id;
    return max;
  }, typeof baselineUpdateId === 'number' ? baselineUpdateId : 0);

  return {
    call: result,
    updates,
    maxUpdateId
  };
}

function buildE2ESummary(mode) {
  return {
    timestamp: new Date().toISOString(),
    mode,
    ok: false,
    observed_update: false,
    observed_reply: false,
    latency_ms: null,
    error_category: null,
    observed_update_source: 'none',
    observed_reply_source: 'none'
  };
}

async function runE2E(args, context) {
  const mode = args.chatId ? 'live' : 'passive';
  const summary = buildE2ESummary(mode);

  const tokenError = classifyTokenError(context.tokenMeta);
  if (tokenError) {
    summary.error_category = tokenError;
    writeJson(args.reportPath, summary);
    return summary;
  }

  const getMe = await telegramCall(context.token, 'getMe', Math.min(args.timeoutMs, DEFAULT_TIMEOUT_MS));
  if (getMe.ok !== true) {
    summary.error_category = getMe.error_category || 'telegram_error';
    writeJson(args.reportPath, summary);
    return summary;
  }

  if (mode === 'passive') {
    console.log('Passive mode: send /start to the bot now; waiting for inbound update evidence...');
  }

  const startTs = Date.now();
  const pollStart = await pollUpdatesSince(context.token, null, Math.min(args.timeoutMs, DEFAULT_TIMEOUT_MS));
  let baselineUpdateId = typeof pollStart.maxUpdateId === 'number' ? pollStart.maxUpdateId : null;

  let probeMessageId = null;
  let probeTag = null;

  if (mode === 'live') {
    probeTag = `openclaw-e2e-${Date.now().toString(36)}-${Math.floor(Math.random() * 10000).toString(36)}`;
    const sendProbe = await telegramCall(
      context.token,
      'sendMessage',
      Math.min(args.timeoutMs, DEFAULT_TIMEOUT_MS),
      {
        chat_id: args.chatId,
        text: `OpenClaw telegram e2e probe ${probeTag}`,
        disable_notification: true
      }
    );

    if (sendProbe.ok !== true) {
      summary.error_category = sendProbe.error_category || 'telegram_error';
      writeJson(args.reportPath, summary);
      return summary;
    }

    probeMessageId = typeof sendProbe.parsed?.result?.message_id === 'number' ? sendProbe.parsed.result.message_id : null;

    summary.observed_reply = true;
    summary.observed_reply_source = 'sendMessage_ack';
    if (probeMessageId !== null) {
      summary.observed_update = true;
      summary.observed_update_source = 'sendMessage_ack';
      summary.latency_ms = Date.now() - startTs;
    }
  }

  const watcher = args.followOpenclawLogs ? initLogWatcher() : null;
  const deadline = Date.now() + args.timeoutMs;
  let logInbound = false;
  let logOutbound = false;

  while (Date.now() < deadline) {
    const remaining = deadline - Date.now();
    const pollResult = await pollUpdatesSince(context.token, baselineUpdateId, Math.min(remaining, DEFAULT_TIMEOUT_MS));

    if (pollResult.call.error_category && pollResult.call.error_category !== 'network_error') {
      summary.error_category = pollResult.call.error_category;
      break;
    }

    if (pollResult.updates.length > 0) {
      baselineUpdateId = pollResult.maxUpdateId;

      for (const update of pollResult.updates) {
        const meta = sanitizeUpdateMeta(update);
        summary.observed_update = true;
        if (summary.observed_update_source === 'none') {
          summary.observed_update_source = 'getUpdates';
        }
        if (summary.latency_ms === null) {
          summary.latency_ms = Date.now() - startTs;
        }

        const payload = update && (update.message || update.edited_message || update.channel_post || update.edited_channel_post);
        const text = typeof payload?.text === 'string' ? payload.text : '';

        if (mode === 'live') {
          const hasProbeTag = probeTag && text.includes(probeTag);
          const isReplyToProbe = probeMessageId !== null && meta.reply_to_message_id === probeMessageId;
          const isBotMessage = meta.from_is_bot === true;
          if (hasProbeTag || isReplyToProbe || isBotMessage) {
            summary.observed_reply = true;
            if (summary.observed_reply_source === 'none' || summary.observed_reply_source === 'sendMessage_ack') {
              summary.observed_reply_source = 'getUpdates';
            }
          }
        } else {
          if (meta.from_is_bot === true) {
            summary.observed_reply = true;
            summary.observed_reply_source = 'getUpdates';
          }
        }
      }
    }

    if (watcher) {
      const marks = watcher.poll();
      logInbound = logInbound || marks.sawInboundPath;
      logOutbound = logOutbound || marks.sawOutboundPath;
      if (marks.sawInboundPath && summary.observed_update_source === 'none') {
        summary.observed_update_source = 'openclaw_logs';
      }
      if (marks.sawOutboundPath && summary.observed_reply_source === 'none') {
        summary.observed_reply_source = 'openclaw_logs';
      }
    }

    if (mode === 'live' && summary.observed_update && summary.observed_reply) {
      break;
    }

    await sleep(LOG_SCAN_INTERVAL_MS);
  }

  if (mode === 'passive') {
    summary.ok = false;
    if (!summary.error_category) {
      summary.error_category = 'passive_mode_observation_only';
    }
  } else {
    if (!summary.error_category) {
      summary.ok = summary.observed_update && summary.observed_reply;
      if (!summary.ok) {
        if (args.followOpenclawLogs && (logInbound || logOutbound)) {
          summary.error_category = 'e2e_partial_observation';
        } else {
          summary.error_category = 'e2e_timeout';
        }
      }
    }
  }

  writeJson(args.reportPath, summary);
  return summary;
}

async function runStandardDiagnostics(args, context) {
  const summary = {
    token_source: context.tokenSource,
    config_path_checked: args.configPath,
    config_read_ok: context.config.configReadOk,
    config_error: context.config.configError || null,
    telegram_mode: context.config.telegramMode || null,
    service_env: readLaunchAgentSummary(),
    ...context.tokenMeta
  };

  console.log(JSON.stringify(summary, null, 2));

  const tokenError = classifyTokenError(context.tokenMeta);
  if (tokenError) {
    console.error(`DIAG_FAIL: ${tokenError}`);
    process.exit(2);
  }

  const getMe = await telegramCall(context.token, 'getMe', args.timeoutMs);
  delete getMe.parsed;
  console.log(JSON.stringify({ getMe }, null, 2));

  const getWebhookInfo = await telegramCall(context.token, 'getWebhookInfo', args.timeoutMs);
  const isWebhookSet = webhookSet(getWebhookInfo);
  delete getWebhookInfo.parsed;
  console.log(JSON.stringify({ getWebhookInfo, webhook_url_set: isWebhookSet }, null, 2));

  if (args.resetWebhook) {
    const deleteWebhook = await telegramCall(
      context.token,
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

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const config = loadConfigToken(args.configPath);
  const envToken = process.env.TELEGRAM_BOT_TOKEN;
  const token = typeof envToken === 'string' && envToken.length > 0 ? envToken : config.token;
  const tokenSource = typeof envToken === 'string' && envToken.length > 0 ? 'env' : 'config';
  const tokenMeta = inspectToken(token);

  const context = {
    config,
    token,
    tokenSource,
    tokenMeta
  };

  if (args.e2e) {
    const result = await runE2E(args, context);
    console.log(JSON.stringify({ e2e_summary_path: args.reportPath, ...result }, null, 2));
    if (result.ok !== true) {
      process.exit(4);
    }
    return;
  }

  await runStandardDiagnostics(args, context);
}

if (require.main === module) {
  main().catch((error) => {
    console.error(`DIAG_FAIL: ${String(error && error.message ? error.message : error).slice(0, 200)}`);
    process.exit(1);
  });
}

module.exports = {
  parseArgs,
  inspectToken,
  redactToken,
  sanitizeUpdateMeta,
  buildE2ESummary,
  classifyTokenError,
  classifyHttpError
};
