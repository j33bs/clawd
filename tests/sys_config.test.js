const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { loadConfig, watchConfig, envOverridesToObject } = require('../sys/config');

function writeToml(targetPath, body) {
  fs.mkdirSync(path.dirname(targetPath), { recursive: true });
  fs.writeFileSync(targetPath, body, 'utf8');
}

async function main() {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sys-config-test-'));
  const configPath = path.join(tmpDir, 'config.toml');

  writeToml(
    configPath,
    [
      '[models]',
      'default = "openai/gpt-5-chat-latest"',
      '',
      '[scheduler]',
      'tick_seconds = 300',
      'max_concurrency = 1',
      '',
      '[feature_flags]',
      'system_evolution_enabled = false',
      'semantic_graph_enabled = false',
      'renderer_enabled = false',
      'scheduler_enabled = false',
      'maintenance_enabled = false',
      'breath_module_enabled = false',
      '',
      '[paths]',
      'root = "."',
      'state_dir = "sys/state"',
      'templates_dir = "sys/templates"',
      'log_dir = "logs"',
      '',
      '[evolution]',
      'mode = "prototype"',
      'enable_hot_reload = true',
      '',
      '[knowledge.breath]',
      'evidence_manifest = "sys/knowledge/breath/evidence/manifest.json"',
      '',
      '[system2]',
      'feature_enabled = false',
      'workspace_path = "."',
      'identity_path = "IDENTITY.md"',
      'policy_version = "1.0.0"',
      'tool_allowlist_path = "core/system2/tool_allowlist.readonly.json"',
      'tool_allowlist_hash = "d5322d387a1bc76dd5b87f4b36b05be5f63a4e207d908e9b029a1eb8cdc732be"',
      'federation_enabled = false',
      'federation_external_root = "/Users/heathyeager/clawd_external"',
      'litellm_endpoint = "http://127.0.0.1:4000/v1"',
      'use_litellm_proxy = false',
      'envelope_signing_key_env = "SYSTEM2_ENVELOPE_HMAC_KEY"',
      'event_log_path = "sys/state/system2/events.jsonl"',
      'sync_cursor_path = "sys/state/system2/sync_cursor.json"',
      'tool_plane_enabled = false'
    ].join('\n')
  );

  try {
    const overrides = envOverridesToObject({
      SYS__MODELS__DEFAULT: 'openai/gpt-5.1-codex-mini',
      SYS__SCHEDULER__TICK_SECONDS: '120'
    });

    assert.strictEqual(overrides.models.default, 'openai/gpt-5.1-codex-mini');
    assert.strictEqual(overrides.scheduler.tick_seconds, 120);
    console.log('PASS env override object parsing');
  } catch (error) {
    console.error('FAIL env override object parsing');
    console.error(error.message);
    process.exit(1);
  }

  try {
    const config = loadConfig({
      configPath,
      env: {
        SYS__MODELS__DEFAULT: 'openai/gpt-5.1-codex-mini'
      },
      cliOverrides: {
        models: {
          default: 'openai/gpt-5-chat-latest'
        }
      }
    });

    assert.strictEqual(config.models.default, 'openai/gpt-5-chat-latest');
    assert.strictEqual(config.scheduler.tick_seconds, 300);
    console.log('PASS config precedence defaults < toml < env < cli');
  } catch (error) {
    console.error('FAIL config precedence defaults < toml < env < cli');
    console.error(error.message);
    process.exit(1);
  }

  await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      cleanup();
      reject(new Error('hot reload event did not fire'));
    }, 1500);

    const cleanup = watchConfig({
      configPath,
      onReload(event) {
        try {
          assert.strictEqual(event.type, 'config_hot_reload');
          assert.strictEqual(event.config.models.default, 'openai/gpt-5.1-codex-mini');
          clearTimeout(timeout);
          cleanup();
          resolve();
        } catch (error) {
          clearTimeout(timeout);
          cleanup();
          reject(error);
        }
      },
      onError(error) {
        clearTimeout(timeout);
        cleanup();
        reject(error);
      }
    });

    setTimeout(() => {
      writeToml(
        configPath,
        fs
          .readFileSync(configPath, 'utf8')
          .replace('openai/gpt-5-chat-latest', 'openai/gpt-5.1-codex-mini')
      );
    }, 100);
  });

  console.log('PASS config hot reload signal');
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
