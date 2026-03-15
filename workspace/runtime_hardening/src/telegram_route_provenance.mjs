import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';

function readJsonIfExists(filePath) {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch {
    return null;
  }
}

function appendJsonl(filePath, record) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.appendFileSync(filePath, `${JSON.stringify(record)}\n`, 'utf8');
}

function readTextIfExists(filePath) {
  try {
    return fs.readFileSync(filePath, 'utf8');
  } catch {
    return '';
  }
}

function sha256(input) {
  return crypto.createHash('sha256').update(String(input), 'utf8').digest('hex');
}

function normalizeChatId(value) {
  if (value == null) return null;
  const raw = String(value).trim();
  return raw ? raw : null;
}

function resolveStateDir(env = process.env, cwd = process.cwd(), homedir = os.homedir()) {
  if (typeof env.OPENCLAW_STATE_DIR === 'string' && env.OPENCLAW_STATE_DIR.trim()) {
    return path.resolve(env.OPENCLAW_STATE_DIR.trim());
  }
  if (typeof env.OPENCLAW_CONFIG_PATH === 'string' && env.OPENCLAW_CONFIG_PATH.trim()) {
    return path.dirname(path.resolve(env.OPENCLAW_CONFIG_PATH.trim()));
  }
  if (typeof env.OPENCLAW_HOME === 'string' && env.OPENCLAW_HOME.trim()) {
    const candidate = path.resolve(env.OPENCLAW_HOME.trim(), '.openclaw');
    if (fs.existsSync(candidate)) return candidate;
  }
  const cwdCandidate = path.resolve(cwd, '.openclaw');
  if (fs.existsSync(cwdCandidate)) return cwdCandidate;
  return path.resolve(homedir, '.openclaw');
}

function resolveWorkspaceRoot(env = process.env, cwd = process.cwd()) {
  if (typeof env.WORKSPACE_ROOT === 'string' && env.WORKSPACE_ROOT.trim()) {
    return path.resolve(env.WORKSPACE_ROOT.trim());
  }
  if (typeof env.OPENCLAW_HOME === 'string' && env.OPENCLAW_HOME.trim()) {
    return path.resolve(env.OPENCLAW_HOME.trim());
  }
  return path.resolve(cwd);
}

function buildSurfaceOverlay({ surface = 'telegram', includeMemory = true, mode = 'conversation' } = {}) {
  const normalizedSurface = String(surface || 'unknown').trim().toLowerCase() || 'unknown';
  const normalizedMode = String(mode || 'conversation').trim().toLowerCase() || 'conversation';
  const memoryMode = includeMemory ? 'memory:on' : 'memory:off';
  const overlayId = `surface:${normalizedSurface}|mode:${normalizedMode}|${memoryMode}`;
  const overlayText = [
    '## Active surface',
    '',
    `- surface: ${normalizedSurface}`,
    `- mode: ${normalizedMode}`,
    `- memory: ${includeMemory ? 'included' : 'excluded'}`,
    '- response goal: Codex-direct quality adapted to chat constraints',
    '- keep file/path references explicit when repo-grounded',
    '- make execution state and residual uncertainty concrete'
  ].join('\n');
  return { overlayId, overlayText };
}

function buildConversationKernelPacket(
  { workspaceRoot = resolveWorkspaceRoot(), surface = 'telegram', includeMemory = true, mode = 'conversation' } = {}
) {
  const kernelPath = path.join(workspaceRoot, 'nodes', 'c_lawd', 'CONVERSATION_KERNEL.md');
  const userPath = path.join(workspaceRoot, 'USER.md');
  const memoryPath = path.join(workspaceRoot, 'MEMORY.md');
  const parts = [];

  const kernelText = readTextIfExists(kernelPath).trim();
  if (kernelText) parts.push(kernelText);

  const userText = readTextIfExists(userPath).trim();
  if (userText) parts.push(`## USER profile\n\n${userText}`);

  if (includeMemory) {
    const memoryText = readTextIfExists(memoryPath).trim();
    if (memoryText) parts.push(`## MEMORY\n\n${memoryText}`);
  }

  const { overlayId, overlayText } = buildSurfaceOverlay({ surface, includeMemory, mode });
  parts.push(overlayText);
  const promptText = parts.filter(Boolean).join('\n\n').trim();

  return {
    kernelId: `c_lawd:${overlayId}`,
    kernelHash: promptText ? sha256(promptText) : null,
    surfaceOverlay: overlayId,
    promptText
  };
}

function transcriptSessionId(entry) {
  const fromReport = entry?.systemPromptReport?.sessionId;
  if (typeof fromReport === 'string' && fromReport.trim()) return fromReport.trim();
  const fromId = entry?.id;
  if (typeof fromId === 'string' && fromId.trim()) return fromId.trim();
  return null;
}

function deliveryTargetsChat(deliveryTo, chatId) {
  if (!deliveryTo || !chatId) return false;
  return deliveryTo === `telegram:${chatId}` || deliveryTo.startsWith(`telegram:${chatId}:topic:`);
}

function findTelegramSession(store, chatId, accountId = null) {
  const matches = [];
  for (const [sessionKey, entry] of Object.entries(store || {})) {
    const delivery = entry?.deliveryContext;
    if (delivery?.channel !== 'telegram') continue;
    if (!deliveryTargetsChat(delivery?.to, chatId)) continue;
    if (accountId && delivery?.accountId && delivery.accountId !== accountId) continue;
    matches.push({ sessionKey, entry });
  }
  matches.sort((left, right) => {
    const leftUpdated = Number(left.entry?.updatedAt || 0);
    const rightUpdated = Number(right.entry?.updatedAt || 0);
    return rightUpdated - leftUpdated;
  });
  return matches[0] || null;
}

function readLatestAssistantMessage(transcriptPath) {
  try {
    const lines = fs.readFileSync(transcriptPath, 'utf8').split('\n').filter(Boolean);
    for (let index = lines.length - 1; index >= 0; index -= 1) {
      const parsed = JSON.parse(lines[index]);
      if (parsed?.type !== 'message') continue;
      if (parsed?.message?.role !== 'assistant') continue;
      return parsed;
    }
  } catch {
    return null;
  }
  return null;
}

function buildTelegramRouteProvenance({
  chatId,
  accountId = null,
  responseMessageId = null,
  stateDir = resolveStateDir(),
  workspaceRoot = resolveWorkspaceRoot(),
  now = new Date()
} = {}) {
  const normalizedChatId = normalizeChatId(chatId);
  if (!normalizedChatId) return null;

  const sessionsPath = path.join(stateDir, 'agents', 'main', 'sessions', 'sessions.json');
  const store = readJsonIfExists(sessionsPath);
  if (!store || typeof store !== 'object') return null;

  const match = findTelegramSession(store, normalizedChatId, accountId);
  if (!match) return null;

  const sessionId = transcriptSessionId(match.entry);
  const transcriptPath = sessionId
    ? path.join(stateDir, 'agents', 'main', 'sessions', `${sessionId}.jsonl`)
    : null;
  const assistant = transcriptPath ? readLatestAssistantMessage(transcriptPath) : null;
  const assistantMessage = assistant?.message || null;
  const kernel = buildConversationKernelPacket({
    workspaceRoot,
    surface: 'telegram',
    includeMemory: true,
    mode: 'conversation'
  });

  return {
    ts: now.toISOString(),
    channel: 'telegram',
    chat_id: normalizedChatId,
    response_message_id: responseMessageId ? String(responseMessageId) : null,
    account_id: match.entry?.deliveryContext?.accountId ?? accountId ?? null,
    delivery_to: match.entry?.deliveryContext?.to ?? null,
    session_key: match.sessionKey,
    session_id: sessionId,
    session_updated_at: match.entry?.updatedAt ?? null,
    provider: assistantMessage?.provider ?? match.entry?.modelProvider ?? match.entry?.systemPromptReport?.provider ?? null,
    model: assistantMessage?.model ?? match.entry?.model ?? match.entry?.systemPromptReport?.model ?? null,
    api: assistantMessage?.api ?? null,
    stop_reason: assistantMessage?.stopReason ?? null,
    kernel_id: kernel.kernelId,
    kernel_hash: kernel.kernelHash,
    surface_overlay: kernel.surfaceOverlay,
    assistant_message_id: assistant?.id ?? null,
    assistant_timestamp: assistant?.timestamp ?? null,
    system_prompt_provider: match.entry?.systemPromptReport?.provider ?? null,
    system_prompt_model: match.entry?.systemPromptReport?.model ?? null,
    system_prompt_generated_at: match.entry?.systemPromptReport?.generatedAt ?? null,
    route_source: assistant ? 'session_transcript_latest_assistant' : 'session_store_fallback'
  };
}

function auditTelegramRouteProvenance({
  chatId,
  accountId = null,
  responseMessageId = null,
  stateDir,
  workspaceRoot,
  logPath,
  now
} = {}) {
  const record = buildTelegramRouteProvenance({
    chatId,
    accountId,
    responseMessageId,
    stateDir,
    workspaceRoot,
    now
  });
  if (!record) return null;
  if (logPath) appendJsonl(logPath, record);
  return record;
}

export {
  auditTelegramRouteProvenance,
  buildConversationKernelPacket,
  buildSurfaceOverlay,
  buildTelegramRouteProvenance,
  resolveStateDir,
  resolveWorkspaceRoot
};
