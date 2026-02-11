'use strict';

const DEFAULT_CONFIG = {
  feature_flags: {
    system_evolution_enabled: false,
    semantic_graph_enabled: false,
    renderer_enabled: false,
    scheduler_enabled: false,
    maintenance_enabled: false,
    breath_module_enabled: false
  },
  paths: {
    root: '.',
    state_dir: 'sys/state',
    templates_dir: 'sys/templates',
    log_dir: 'logs'
  },
  models: {
    default: 'openai/gpt-5-chat-latest'
  },
  scheduler: {
    tick_seconds: 300,
    max_concurrency: 1
  },
  evolution: {
    mode: 'prototype',
    enable_hot_reload: true
  },
  knowledge: {
    breath: {
      evidence_manifest: 'sys/knowledge/breath/evidence/manifest.json'
    }
  },
  system2: {
    feature_enabled: false,
    workspace_path: '.',
    identity_path: 'IDENTITY.md',
    policy_version: '1.0.0',
    tool_allowlist_path: 'core/system2/tool_allowlist.readonly.json',
    tool_allowlist_hash: 'd5322d387a1bc76dd5b87f4b36b05be5f63a4e207d908e9b029a1eb8cdc732be',
    federation_enabled: false,
    federation_external_root: '/Users/heathyeager/clawd_external',
    litellm_endpoint: 'http://127.0.0.1:4000/v1',
    use_litellm_proxy: false,
    envelope_signing_key_env: 'SYSTEM2_ENVELOPE_HMAC_KEY',
    event_log_path: 'sys/state/system2/events.jsonl',
    sync_cursor_path: 'sys/state/system2/sync_cursor.json',
    tool_plane_enabled: false
  }
};

module.exports = {
  DEFAULT_CONFIG
};
