import test from 'node:test';
import assert from 'node:assert/strict';

import { clearConfigCache, validateConfig } from '../src/config.mjs';

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

test('config validation fails when ANTHROPIC_API_KEY is missing', () => {
  withEnv({ ANTHROPIC_API_KEY: undefined, NODE_ENV: 'test' }, () => {
    assert.throws(() => validateConfig(process.env), /ANTHROPIC_API_KEY/);
  });
});

test('config validation rejects invalid NODE_ENV', () => {
  withEnv({ ANTHROPIC_API_KEY: 'abc123', NODE_ENV: 'staging' }, () => {
    assert.throws(() => validateConfig(process.env), /NODE_ENV/);
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
    }
  );
});
