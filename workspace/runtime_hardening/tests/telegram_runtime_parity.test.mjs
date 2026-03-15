import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import {
  compareTelegramRuntimeParity,
  verifyTelegramRuntimeParity
} from '../src/telegram_runtime_parity.mjs';

function makeTempDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'telegram-runtime-parity-'));
}

function writeJson(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(value, null, 2), 'utf8');
}

test('compareTelegramRuntimeParity reports mismatch when telegram policy provider is absent from runtime config', () => {
  const result = compareTelegramRuntimeParity({
    policy: {
      providers: {
        openai_gpt54_chat: {
          models: [{ id: 'gpt-5.4' }]
        }
      },
      routing: {
        surface_profiles: {
          telegram: {
            intents: {
              conversation: {
                order: ['openai_gpt54_chat']
              }
            },
            capability_router: {
              chatProvider: 'openai_gpt54_chat'
            }
          }
        }
      }
    },
    runtimeConfig: {
      models: {
        providers: {
          local_vllm_assistant: {
            models: [{ id: 'local-assistant' }]
          }
        }
      }
    }
  });

  assert.equal(result.status, 'mismatch');
  assert.equal(result.mismatches.length, 1);
  assert.equal(result.mismatches[0].provider, 'openai_gpt54_chat');
  assert.equal(result.mismatches[0].status, 'missing_provider');
});

test('verifyTelegramRuntimeParity passes when runtime config exposes telegram policy providers and models', () => {
  const root = makeTempDir();
  const policyPath = path.join(root, 'workspace', 'policy', 'llm_policy.json');
  const runtimeConfigPath = path.join(root, '.openclaw', 'openclaw.json');

  writeJson(policyPath, {
    providers: {
      openai_gpt54_chat: {
        models: [{ id: 'gpt-5.4' }]
      },
      local_vllm_assistant: {
        models: [{ id: 'local-assistant' }]
      }
    },
    routing: {
      surface_profiles: {
        telegram: {
          intents: {
            conversation: {
              order: ['openai_gpt54_chat', 'local_vllm_assistant']
            }
          },
          capability_router: {
            chatProvider: 'openai_gpt54_chat',
            planningProvider: 'openai_gpt54_chat',
            reasoningProvider: 'openai_gpt54_chat',
            codeProvider: 'openai_gpt54_chat',
            smallCodeProvider: 'local_vllm_assistant'
          }
        }
      }
    }
  });
  writeJson(runtimeConfigPath, {
    models: {
      providers: {
        openai_gpt54_chat: {
          models: [{ id: 'gpt-5.4' }]
        },
        local_vllm_assistant: {
          models: [{ id: 'local-assistant' }]
        }
      }
    }
  });

  const result = verifyTelegramRuntimeParity({
    repoRoot: root,
    policyPath,
    runtimeConfigPath
  });

  assert.equal(result.status, 'ok');
  assert.equal(result.mismatches.length, 0);
  assert.equal(result.providers.length, 2);
});

test('compareTelegramRuntimeParity accepts runtime model matches from differently named providers', () => {
  const result = compareTelegramRuntimeParity({
    policy: {
      providers: {
        minimax_m25: {
          models: [{ id: 'minimax-portal/MiniMax-M2.5' }]
        }
      },
      routing: {
        surface_profiles: {
          telegram: {
            intents: {
              conversation: {
                order: ['minimax_m25']
              }
            }
          }
        }
      }
    },
    runtimeConfig: {
      models: {
        providers: {
          'minimax-portal': {
            models: [{ id: 'MiniMax-M2.5' }]
          }
        }
      }
    }
  });

  assert.equal(result.status, 'ok');
  assert.equal(result.mismatches.length, 0);
  assert.deepEqual(result.providers[0].runtime_matching_providers, ['minimax-portal']);
});
