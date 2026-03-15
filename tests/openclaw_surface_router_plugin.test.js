const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const pluginModule = require('/Users/heathyeager/clawd/plugins/openclaw_surface_router_plugin/index.js');

function withTempStateDir(fn) {
  const stateDir = fs.mkdtempSync(path.join(os.tmpdir(), 'openclaw-surface-router-'));
  const previous = process.env.OPENCLAW_STATE_DIR;
  process.env.OPENCLAW_STATE_DIR = stateDir;
  try {
    fn(stateDir);
  } finally {
    if (previous === undefined) delete process.env.OPENCLAW_STATE_DIR;
    else process.env.OPENCLAW_STATE_DIR = previous;
  }
}

function writeJson(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(value, null, 2));
}

test('resolveTelegramRuntimeOverride selects OpenAI 5.4 for telegram when no manual override exists', () => {
  withTempStateDir((stateDir) => {
    writeJson(path.join(stateDir, 'agents', 'main', 'sessions', 'sessions.json'), {
      'agent:main:main': {
        deliveryContext: {
          channel: 'telegram',
          to: 'telegram:8159253715',
          accountId: 'default'
        }
      }
    });
    const result = pluginModule._test.resolveTelegramRuntimeOverride({
      channelId: 'telegram',
      sessionKey: 'agent:main:main'
    });
    assert.equal(result.providerOverride, 'openai-codex');
    assert.equal(result.modelOverride, 'gpt-5.4');
    assert.equal(result.route.policyProfile, 'surface:telegram');
  });
});

test('resolveTelegramRuntimeOverride respects manual session overrides', () => {
  withTempStateDir((stateDir) => {
    writeJson(path.join(stateDir, 'agents', 'main', 'sessions', 'sessions.json'), {
      'agent:main:main': {
        providerOverride: 'xai',
        modelOverride: 'grok-4-1-fast',
        deliveryContext: {
          channel: 'telegram',
          to: 'telegram:8159253715',
          accountId: 'default'
        }
      }
    });
    const result = pluginModule._test.resolveTelegramRuntimeOverride({
      channelId: 'telegram',
      sessionKey: 'agent:main:main'
    });
    assert.equal(result, null);
  });
});

test('buildTelegramPromptInjection loads the c_lawd kernel for telegram', () => {
  const result = pluginModule._test.buildTelegramPromptInjection({
    channelId: 'telegram',
    sessionKey: 'agent:main:main'
  });
  assert.equal(typeof result.prependSystemContext, 'string');
  assert.match(result.prependSystemContext, /## USER profile/);
  assert.match(result.prependSystemContext, /## MEMORY/);
  assert.match(result.prependSystemContext, /## Active surface/);
  assert.match(result.prependSystemContext, /c_lawd/i);
});

test('buildTelegramLlmOutputRecord records actual llm output metadata', () => {
  withTempStateDir((stateDir) => {
    writeJson(path.join(stateDir, 'agents', 'main', 'sessions', 'sessions.json'), {
      'agent:main:main': {
        deliveryContext: {
          channel: 'telegram',
          to: 'telegram:8159253715',
          accountId: 'default'
        },
        systemPromptReport: {
          provider: 'openai-codex',
          model: 'gpt-5.4'
        }
      }
    });
    const record = pluginModule._test.buildTelegramLlmOutputRecord(
      {
        runId: 'run-1',
        sessionId: 'session-1',
        provider: 'openai-codex',
        model: 'gpt-5.4'
      },
      {
        channelId: 'telegram',
        sessionKey: 'agent:main:main',
        messageProvider: 'telegram'
      }
    );
    assert.equal(record.phase, 'llm_output');
    assert.equal(record.provider, 'openai-codex');
    assert.equal(record.model, 'gpt-5.4');
    assert.equal(record.policy_profile, 'surface:telegram');
    assert.equal(record.delivery_to, 'telegram:8159253715');
    assert.equal(record.kernel_id, 'c_lawd:surface:telegram|mode:conversation|memory:on');
    assert.equal(record.surface_overlay, 'surface:telegram|mode:conversation|memory:on');
    assert.match(record.kernel_hash, /^[a-f0-9]{64}$/);
  });
});

test('buildConversationKernelPacket matches the shared telegram kernel contract', () => {
  const packet = pluginModule._test.buildConversationKernelPacket({
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
