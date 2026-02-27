import test from 'node:test';
import assert from 'node:assert/strict';

import { clearConfigCache, redactConfigForLogs, validateConfig } from '../src/config.mjs';

function withEnv(patch, fn) {
  const previous = {};
  for (const key of Object.keys(patch)) {
    previous[key] = process.env[key];
    if (patch[key] === undefined) {
      delete process.env[key];
    } else {
      process.env[key] = patch[key];
    }
  }

  try {
    fn();
  } finally {
    for (const key of Object.keys(patch)) {
      if (previous[key] === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = previous[key];
      }
    }
    clearConfigCache();
  }
}

test('config validation passes without ANTHROPIC_API_KEY when anthropic is disabled', () => {
  withEnv({ ANTHROPIC_API_KEY: undefined, OPENCLAW_PROVIDER_ALLOWLIST: 'local_vllm,minimax-portal', NODE_ENV: 'test' }, () => {
    assert.doesNotThrow(() => validateConfig(process.env));
  });
});

test('config validation fails when ANTHROPIC_API_KEY is missing and anthropic is enabled', () => {
  withEnv({ ANTHROPIC_API_KEY: undefined, OPENCLAW_PROVIDER_ALLOWLIST: 'anthropic,local_vllm', NODE_ENV: 'test' }, () => {
    assert.throws(
      () => validateConfig(process.env),
      /ANTHROPIC_API_KEY: required non-empty value is missing/
    );
  });
});

test('config validation ignores default model/provider for anthropic enablement when allowlist is unset', () => {
  withEnv(
    {
      ANTHROPIC_API_KEY: undefined,
      OPENCLAW_PROVIDER_ALLOWLIST: undefined,
      OPENCLAW_DEFAULT_PROVIDER: 'anthropic',
      OPENCLAW_DEFAULT_MODEL: 'anthropic/claude-sonnet',
      NODE_ENV: 'test'
    },
    () => {
      assert.doesNotThrow(() => validateConfig(process.env));
      const cfg = validateConfig(process.env);
      assert.equal(cfg.anthropicEnabled, false);
    }
  );
});

test('config validation rejects invalid NODE_ENV', () => {
  withEnv({ ANTHROPIC_API_KEY: 'abc123', NODE_ENV: 'staging' }, () => {
    assert.throws(() => validateConfig(process.env), /NODE_ENV/);
  });
});

test('config validation rejects invalid TELEGRAM_REPLY_MODE', () => {
  withEnv({ ANTHROPIC_API_KEY: 'abc123', NODE_ENV: 'test', TELEGRAM_REPLY_MODE: 'sometimes' }, () => {
    assert.throws(() => validateConfig(process.env), /TELEGRAM_REPLY_MODE/);
  });
});

test('config validation returns normalized defaults', () => {
  withEnv(
    {
      ANTHROPIC_API_KEY: 'abc123',
      NODE_ENV: 'test',
      WORKSPACE_ROOT: process.cwd(),
      AGENT_WORKSPACE_ROOT: '.agent_workspace',
      SKILLS_ROOT: 'skills'
    },
    () => {
      const cfg = validateConfig(process.env);
      assert.equal(cfg.nodeEnv, 'test');
      assert.equal(cfg.sessionMax > 0, true);
      assert.equal(cfg.historyMaxMessages > 0, true);
      assert.equal(cfg.workspaceRoot, process.cwd());
      assert.equal(cfg.agentWorkspaceRoot.endsWith('.agent_workspace'), true);
      assert.equal(cfg.skillsRoot.endsWith('skills'), true);
      assert.equal(cfg.telegramReplyMode, 'never');
    }
  );
});

test('redacted logs omit anthropicApiKey when anthropic is disabled', () => {
  withEnv({ ANTHROPIC_API_KEY: 'abc123', OPENCLAW_PROVIDER_ALLOWLIST: 'local_vllm', NODE_ENV: 'test' }, () => {
    const cfg = validateConfig(process.env);
    const redacted = redactConfigForLogs(cfg);
    assert.equal(redacted.anthropicEnabled, false);
    assert.equal(Object.hasOwn(redacted, 'anthropicApiKey'), false);
  });
});
