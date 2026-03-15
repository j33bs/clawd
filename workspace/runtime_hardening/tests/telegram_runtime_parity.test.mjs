import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import {
  collectEnabledRuntimePlugins,
  compareTelegramRuntimeParity,
  resolveDefaultPaths,
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
  assert.equal(result.mismatches.length, 2);
  assert.equal(result.mismatches[0].provider, 'openai_gpt54_chat');
  assert.equal(result.mismatches[0].status, 'missing_provider');
  assert.equal(result.mismatches[1].required_plugin, 'openclaw_surface_router_plugin');
  assert.equal(result.mismatches[1].status, 'missing_plugin');
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
    plugins: {
      entries: {
        openclaw_surface_router_plugin: {
          enabled: true
        }
      }
    },
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
  assert.equal(result.plugin.status, 'ok');
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
      plugins: {
        load: {
          paths: ['/tmp/openclaw_surface_router_plugin']
        }
      },
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

test('collectEnabledRuntimePlugins includes enabled entries and linked load paths', () => {
  const result = collectEnabledRuntimePlugins({
    plugins: {
      entries: {
        openclaw_surface_router_plugin: { enabled: true },
        disabled_plugin: { enabled: false }
      },
      load: {
        paths: ['/tmp/custom_plugin.js']
      }
    }
  });

  assert.deepEqual(result, ['custom_plugin', 'openclaw_surface_router_plugin']);
});

test('compareTelegramRuntimeParity accepts agent-default model exposure for openai-codex gpt-5.4', () => {
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
            }
          }
        }
      }
    },
    runtimeConfig: {
      plugins: {
        entries: {
          openclaw_surface_router_plugin: { enabled: true }
        }
      },
      agents: {
        defaults: {
          models: {
            'openai-codex/gpt-5.4': {}
          }
        }
      },
      models: {
        providers: {}
      }
    }
  });

  assert.equal(result.status, 'ok');
  assert.equal(result.mismatches.length, 0);
  assert.deepEqual(result.providers[0].runtime_matching_providers, ['openai-codex']);
});

test('resolveDefaultPaths prefers repo-local state dir when present', () => {
  const root = makeTempDir();
  writeJson(path.join(root, '.openclaw', 'openclaw.json'), { ok: true });
  const paths = resolveDefaultPaths(root);
  assert.equal(paths.runtimeConfigPath, path.join(root, '.openclaw', 'openclaw.json'));
});
