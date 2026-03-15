import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import {
  auditTelegramRouteProvenance,
  buildConversationKernelPacket,
  buildTelegramRouteProvenance
} from '../src/telegram_route_provenance.mjs';

function makeTempDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'telegram-route-provenance-'));
}

function writeJson(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(value, null, 2));
}

function writeTranscript(filePath, records) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(
    filePath,
    records.map((record) => JSON.stringify(record)).join('\n') + '\n',
    'utf8'
  );
}

test('buildTelegramRouteProvenance reads latest assistant metadata for matching telegram chat', () => {
  const stateDir = makeTempDir();
  writeJson(path.join(stateDir, 'agents', 'main', 'sessions', 'sessions.json'), {
    'agent:main:main': {
      modelProvider: 'openai-codex',
      model: 'gpt-5.4',
      updatedAt: 1773574219979,
      deliveryContext: {
        channel: 'telegram',
        to: 'telegram:8159253715',
        accountId: 'default'
      },
      systemPromptReport: {
        sessionId: 'session-123',
        provider: 'openai-codex',
        model: 'gpt-5.4',
        generatedAt: 1773574210522
      }
    }
  });
  writeTranscript(path.join(stateDir, 'agents', 'main', 'sessions', 'session-123.jsonl'), [
    {
      type: 'message',
      id: 'user-1',
      message: {
        role: 'user',
        content: [{ type: 'text', text: 'hello' }]
      }
    },
    {
      type: 'message',
      id: 'assistant-1',
      timestamp: '2026-03-15T11:30:19.469Z',
      message: {
        role: 'assistant',
        api: 'openai-codex-responses',
        provider: 'openai-codex',
        model: 'gpt-5.4',
        stopReason: 'stop',
        content: [{ type: 'text', text: 'glad to hear it' }]
      }
    }
  ]);

  const record = buildTelegramRouteProvenance({
    chatId: '8159253715',
    responseMessageId: '4765',
    stateDir,
    now: new Date('2026-03-15T11:30:22.700Z')
  });

  assert.equal(record.chat_id, '8159253715');
  assert.equal(record.response_message_id, '4765');
  assert.equal(record.session_key, 'agent:main:main');
  assert.equal(record.provider, 'openai-codex');
  assert.equal(record.model, 'gpt-5.4');
  assert.equal(record.api, 'openai-codex-responses');
  assert.equal(record.route_source, 'session_transcript_latest_assistant');
  assert.equal(record.kernel_id, 'c_lawd:surface:telegram|mode:conversation|memory:on');
  assert.equal(record.surface_overlay, 'surface:telegram|mode:conversation|memory:on');
  assert.match(record.kernel_hash, /^[a-f0-9]{64}$/);
});

test('auditTelegramRouteProvenance appends JSONL record', () => {
  const stateDir = makeTempDir();
  const logPath = path.join(stateDir, 'audit', 'telegram_route_provenance.jsonl');
  writeJson(path.join(stateDir, 'agents', 'main', 'sessions', 'sessions.json'), {
    'agent:main:main': {
      modelProvider: 'openai-codex',
      model: 'gpt-5.4',
      updatedAt: 1773574219979,
      deliveryContext: {
        channel: 'telegram',
        to: 'telegram:8159253715',
        accountId: 'default'
      },
      systemPromptReport: {
        sessionId: 'session-123',
        provider: 'openai-codex',
        model: 'gpt-5.4',
        generatedAt: 1773574210522
      }
    }
  });
  writeTranscript(path.join(stateDir, 'agents', 'main', 'sessions', 'session-123.jsonl'), [
    {
      type: 'message',
      id: 'assistant-1',
      timestamp: '2026-03-15T11:30:19.469Z',
      message: {
        role: 'assistant',
        api: 'openai-codex-responses',
        provider: 'openai-codex',
        model: 'gpt-5.4',
        stopReason: 'stop',
        content: [{ type: 'text', text: 'glad to hear it' }]
      }
    }
  ]);

  const record = auditTelegramRouteProvenance({
    chatId: '8159253715',
    responseMessageId: '4765',
    stateDir,
    logPath,
    now: new Date('2026-03-15T11:30:22.700Z')
  });

  assert.equal(record.response_message_id, '4765');
  const lines = fs.readFileSync(logPath, 'utf8').trim().split('\n');
  assert.equal(lines.length, 1);
  const parsed = JSON.parse(lines[0]);
  assert.equal(parsed.chat_id, '8159253715');
  assert.equal(parsed.provider, 'openai-codex');
  assert.equal(parsed.kernel_id, 'c_lawd:surface:telegram|mode:conversation|memory:on');
});

test('buildTelegramRouteProvenance returns null when no session matches chat id', () => {
  const stateDir = makeTempDir();
  writeJson(path.join(stateDir, 'agents', 'main', 'sessions', 'sessions.json'), {
    'agent:main:main': {
      deliveryContext: {
        channel: 'telegram',
        to: 'telegram:999',
        accountId: 'default'
      }
    }
  });

  const record = buildTelegramRouteProvenance({
    chatId: '8159253715',
    stateDir
  });

  assert.equal(record, null);
});

test('buildConversationKernelPacket matches the shared telegram kernel contract', () => {
  const packet = buildConversationKernelPacket({
    workspaceRoot: '/Users/heathyeager/clawd',
    surface: 'telegram',
    includeMemory: true,
    mode: 'conversation'
  });

  assert.equal(packet.kernelId, 'c_lawd:surface:telegram|mode:conversation|memory:on');
  assert.equal(packet.surfaceOverlay, 'surface:telegram|mode:conversation|memory:on');
  assert.match(packet.kernelHash, /^[a-f0-9]{64}$/);
  assert.match(packet.promptText, /## USER profile/);
  assert.match(packet.promptText, /## MEMORY/);
  assert.match(packet.promptText, /## Active surface/);
});
