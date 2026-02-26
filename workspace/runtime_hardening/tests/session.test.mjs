import test from 'node:test';
import assert from 'node:assert/strict';

import { SessionManager } from '../src/session.mjs';

const TEST_CONFIG = Object.freeze({
  anthropicApiKey: 'test',
  nodeEnv: 'test',
  workspaceRoot: process.cwd(),
  agentWorkspaceRoot: `${process.cwd()}/.agent_workspace`,
  skillsRoot: `${process.cwd()}/skills`,
  sessionTtlMs: 50,
  sessionMax: 2,
  historyMaxMessages: 3,
  mcpServerStartTimeoutMs: 500,
  logLevel: 'silent',
  fsAllowOutsideWorkspace: false
});

test('session manager evicts sessions after ttl', async () => {
  const manager = new SessionManager({
    config: TEST_CONFIG,
    sessionTtlMs: 50,
    sweepIntervalMs: 1_000_000,
    historyMaxMessages: 3,
    maxSessions: 2
  });

  manager.getOrCreateSession('ttl-session');
  const session = manager.getSession('ttl-session');
  session.lastTouchedAt = Date.now() - 1_000;

  const evicted = await manager.sweepExpired(Date.now());
  assert.equal(evicted, 1);
  assert.equal(manager.has('ttl-session'), false);

  await manager.shutdown();
});

test('session manager truncates history to configured maximum', async () => {
  const manager = new SessionManager({
    config: TEST_CONFIG,
    historyMaxMessages: 3,
    sweepIntervalMs: 1_000_000,
    sessionTtlMs: 5_000,
    maxSessions: 4
  });

  manager.appendHistory('history-session', { role: 'user', content: 'm1' });
  manager.appendHistory('history-session', { role: 'assistant', content: 'm2' });
  manager.appendHistory('history-session', { role: 'user', content: 'm3' });
  manager.appendHistory('history-session', { role: 'assistant', content: 'm4' });

  const history = manager.getSession('history-session').history;
  assert.equal(history.length, 3);
  assert.deepEqual(
    history.map((entry) => entry.content),
    ['m2', 'm3', 'm4']
  );

  await manager.shutdown();
});

test('session manager ttl eviction is deterministic under fake timers', async (t) => {
  t.mock.timers.enable({ apis: ['Date'] });
  const manager = new SessionManager({
    config: TEST_CONFIG,
    sessionTtlMs: 50,
    sweepIntervalMs: 1_000_000,
    historyMaxMessages: 3,
    maxSessions: 2
  });

  manager.getOrCreateSession('fake-time-session');
  t.mock.timers.tick(75);

  const evicted = await manager.sweepExpired(Date.now());
  assert.equal(evicted, 1);
  assert.equal(manager.has('fake-time-session'), false);

  await manager.shutdown();
});
