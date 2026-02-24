'use strict';

const path = require('node:path');
const fs = require('node:fs/promises');

function extractEntityUrl(entity) {
  if (!entity || typeof entity !== 'object') return '';
  if (typeof entity.url === 'string') return entity.url;
  if (typeof entity.text_link === 'string') return entity.text_link;
  return '';
}

function shouldDeferTelegramUpdate(msg) {
  const text = String((msg && (msg.text || msg.caption)) || '');
  const lowered = text.toLowerCase();
  if (lowered.includes('arxiv.org/abs/') || lowered.includes('arxiv.org/pdf/')) return true;
  if (/https?:\/\/\S+\.pdf(?:\b|$)/i.test(text)) return true;
  if (text.length > 1000) return true;

  const entities = [];
  if (Array.isArray(msg && msg.entities)) entities.push(...msg.entities);
  if (Array.isArray(msg && msg.caption_entities)) entities.push(...msg.caption_entities);
  if (
    entities.some((entity) => {
      const url = extractEntityUrl(entity).toLowerCase();
      return url.includes('arxiv.org/abs/') || url.includes('arxiv.org/pdf/') || /\.pdf(?:\b|$)/i.test(url);
    })
  ) {
    return true;
  }

  if (msg && (msg.document || msg.video || msg.audio || msg.voice || msg.video_note || msg.animation)) {
    return true;
  }
  return false;
}

async function writeTelegramDeadletter({ dir, basename, payload }) {
  const targetDir = dir || path.join('/tmp', 'openclaw', 'deadletter');
  const base = basename || 'telegram';
  const ts = new Date().toISOString().replace(/[:.]/g, '-');
  const filePath = path.join(targetDir, `${base}-${ts}-${process.pid}.json`);
  await fs.mkdir(targetDir, { recursive: true });
  await fs.writeFile(filePath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
  return { ok: true, path: filePath };
}

function createFastAckTelegramHandler({ processInbound, enqueue }) {
  if (typeof processInbound !== 'function') {
    throw new TypeError('processInbound must be a function');
  }
  const queueFn = typeof enqueue === 'function' ? enqueue : (fn) => setTimeout(fn, 0);

  return async function handle(event) {
    const startedAt = Date.now();
    if (shouldDeferTelegramUpdate(event && event.msg)) {
      queueFn(async () => {
        await processInbound(event);
      });
      return { deferred: true, elapsed_ms: Date.now() - startedAt };
    }
    await processInbound(event);
    return { deferred: false, elapsed_ms: Date.now() - startedAt };
  };
}

module.exports = {
  shouldDeferTelegramUpdate,
  writeTelegramDeadletter,
  createFastAckTelegramHandler
};
