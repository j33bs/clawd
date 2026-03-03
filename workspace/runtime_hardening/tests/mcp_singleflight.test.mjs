import test from 'node:test';
import assert from 'node:assert/strict';

import { McpServerSingleflight } from '../src/mcp_singleflight.mjs';

const TEST_CONFIG = Object.freeze({
  anthropicApiKey: 'test',
  nodeEnv: 'test',
  workspaceRoot: process.cwd(),
  agentWorkspaceRoot: `${process.cwd()}/.agent_workspace`,
  skillsRoot: `${process.cwd()}/skills`,
  sessionTtlMs: 1000,
  sessionMax: 5,
  historyMaxMessages: 20,
  mcpServerStartTimeoutMs: 500,
  logLevel: 'silent',
  fsAllowOutsideWorkspace: false
});

test('singleflight prevents duplicate concurrent starts', async () => {
  let calls = 0;
  const singleflight = new McpServerSingleflight({
    config: TEST_CONFIG,
    timeoutMs: 500,
    startServer: async (key) => {
      calls += 1;
      await new Promise((resolve) => setTimeout(resolve, 10));
      return { key, startedAt: Date.now() };
    }
  });

  const [a, b] = await Promise.all([singleflight.start('same-key'), singleflight.start('same-key')]);
  assert.equal(calls, 1);
  assert.equal(a, b);
});

test('singleflight clears inFlight when start fails so retries can proceed', async () => {
  let calls = 0;
  const singleflight = new McpServerSingleflight({
    config: TEST_CONFIG,
    timeoutMs: 500,
    startServer: async () => {
      calls += 1;
      if (calls === 1) throw Object.assign(new Error('boot failure'), { status: 500 });
      return { ok: true };
    }
  });

  await assert.rejects(singleflight.start('retry-key'), /boot failure/);
  const handle = await singleflight.start('retry-key');

  assert.equal(calls, 2);
  assert.deepEqual(handle, { ok: true });
});
