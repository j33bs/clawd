import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import {
  appendContractSignal,
  _resetRateLimitForTest,
  getResolvedSignalPath,
} from '../workspace/runtime_hardening/src/contract_signal.mjs';

test('appendContractSignal writes jsonl and rate-limits per process', () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'openclaw-contract-'));
  process.env.OPENCLAW_CONTRACT_STATE_DIR = tmp;

  const signalPath = path.join(tmp, 'signals', 'activity.jsonl');
  assert.equal(getResolvedSignalPath(), signalPath);
  _resetRateLimitForTest();

  const first = appendContractSignal('service_request', { path: '/api/x', method: 'GET' }, { minIntervalMs: 10_000 });
  assert.equal(first.ok, true);
  assert.equal(first.skipped, false);
  assert.equal(fs.existsSync(signalPath), true);

  const lines = fs.readFileSync(signalPath, 'utf8').trim().split('\n');
  assert.equal(lines.length, 1);
  const ev = JSON.parse(lines[0]);
  assert.equal(ev.kind, 'service_request');
  assert.equal(ev.meta.path, '/api/x');
  assert.equal(ev.meta.method, 'GET');

  const second = appendContractSignal('service_request', { path: '/api/y' }, { minIntervalMs: 10_000 });
  assert.equal(second.ok, true);
  assert.equal(second.skipped, true);

  const lines2 = fs.readFileSync(signalPath, 'utf8').trim().split('\n');
  assert.equal(lines2.length, 1);

  delete process.env.OPENCLAW_CONTRACT_STATE_DIR;
});

test('getResolvedSignalPath honors env precedence and guarded cwd fallback', () => {
  const originalCwd = process.cwd();
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'openclaw-contract-root-'));
  const explicitWorkspace = fs.mkdtempSync(path.join(os.tmpdir(), 'openclaw-workspace-root-'));
  try {
    fs.mkdirSync(path.join(explicitWorkspace, 'workspace', 'state_runtime', 'contract'), { recursive: true });

    // 2) OPENCLAW_WORKSPACE_ROOT
    process.env.OPENCLAW_WORKSPACE_ROOT = explicitWorkspace;
    delete process.env.OPENCLAW_CONTRACT_STATE_DIR;
    assert.equal(
      getResolvedSignalPath(),
      path.join(explicitWorkspace, 'workspace', 'state_runtime', 'contract', 'signals', 'activity.jsonl')
    );

    // 1) OPENCLAW_CONTRACT_STATE_DIR (highest precedence)
    process.env.OPENCLAW_CONTRACT_STATE_DIR = tmp;
    assert.equal(getResolvedSignalPath(), path.join(tmp, 'signals', 'activity.jsonl'));
    delete process.env.OPENCLAW_CONTRACT_STATE_DIR;

    // 3) cwd fallback only when it contains workspace/state_runtime/contract
    delete process.env.OPENCLAW_WORKSPACE_ROOT;
    process.chdir(tmp);
    assert.notEqual(getResolvedSignalPath(), path.join(tmp, 'workspace', 'state_runtime', 'contract', 'signals', 'activity.jsonl'));

    fs.mkdirSync(path.join(tmp, 'workspace', 'state_runtime', 'contract'), { recursive: true });
    assert.equal(
      getResolvedSignalPath(),
      path.join(tmp, 'workspace', 'state_runtime', 'contract', 'signals', 'activity.jsonl')
    );
  } finally {
    delete process.env.OPENCLAW_CONTRACT_STATE_DIR;
    delete process.env.OPENCLAW_WORKSPACE_ROOT;
    process.chdir(originalCwd);
  }
});
