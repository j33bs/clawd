'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

test('OPENCLAW_QUIESCE=1 blocks tacti events.jsonl writes', () => {
  const repoRoot = path.resolve(__dirname, '..');
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'openclaw-quiesce-'));
  const targetPath = path.join(tempDir, 'events.jsonl');
  const py = `
import importlib.util
import pathlib
import sys

repo_root = pathlib.Path(sys.argv[1])
target = pathlib.Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("tacti_events", str(repo_root / "workspace" / "tacti" / "events.py"))
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)
mod.DEFAULT_PATH = target
mod.PROTECTED_PATH = target
mod.emit("tacti_cr.test.one", {"x": 1})
mod.emit("tacti_cr.test.two", {"x": 2})
print("ok")
`;

  const run = spawnSync('python3', ['-c', py, repoRoot, targetPath], {
    env: { ...process.env, OPENCLAW_QUIESCE: '1' },
    encoding: 'utf8',
  });

  try {
    assert.equal(run.status, 0, run.stderr || run.stdout);
    assert.equal(fs.existsSync(targetPath), false, 'quiesced writer must not create events file');
    const skipLines = (String(run.stderr || '').match(/QUIESCE_SKIP_WRITE file=/g) || []).length;
    assert.equal(skipLines, 1, `expected one quiesce skip log line, got ${skipLines}`);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});
