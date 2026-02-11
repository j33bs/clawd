'use strict';

const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { System2ToolPlane } = require('../core/system2/tool_plane');

function run(name, fn) {
  try {
    fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    console.error(error.message);
    process.exit(1);
  }
}

function setupTmpWorkspace() {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'system2-tool-plane-'));
  fs.mkdirSync(path.join(tmpDir, 'core', 'system2'), { recursive: true });
  fs.writeFileSync(
    path.join(tmpDir, 'core', 'system2', 'tool_allowlist.readonly.json'),
    JSON.stringify(
      {
        version: '1.0.0',
        mode: 'read_only',
        tools: [
          { name: 'list_dir', read_only: true },
          { name: 'read_file', read_only: true }
        ]
      },
      null,
      2
    ),
    'utf8'
  );
  fs.mkdirSync(path.join(tmpDir, 'docs'), { recursive: true });
  fs.writeFileSync(path.join(tmpDir, 'docs', 'a.txt'), 'hello', 'utf8');
  return tmpDir;
}

run('tool plane denies non-allowlisted tool', () => {
  const workspace = setupTmpWorkspace();
  const plane = new System2ToolPlane({ workspaceRoot: workspace });
  const result = plane.executeToolCall({
    tool: 'exec_cmd',
    args: {},
    policy: {
      mode: 'allow_readonly',
      allowed_tools: ['list_dir', 'read_file']
    }
  });
  assert.strictEqual(result.ok, false);
  assert.strictEqual(result.reason, 'tool_not_allowlisted');
});

run('tool plane executes list_dir and writes artifact', () => {
  const workspace = setupTmpWorkspace();
  const plane = new System2ToolPlane({ workspaceRoot: workspace });
  const result = plane.executeToolCall({
    tool: 'list_dir',
    args: { path: '.' },
    policy: {
      mode: 'allow_readonly',
      allowed_tools: ['list_dir', 'read_file']
    }
  });

  assert.strictEqual(result.ok, true);
  assert.ok(Array.isArray(result.redactedOutput.entries));
  assert.ok(result.redactedOutput.entries.includes('docs'));
  assert.ok(fs.existsSync(result.artifactRef));
});

run('tool plane blocks read_file outside workspace', () => {
  const workspace = setupTmpWorkspace();
  const plane = new System2ToolPlane({ workspaceRoot: workspace });
  const result = plane.executeToolCall({
    tool: 'read_file',
    args: { path: '../outside.txt' },
    policy: {
      mode: 'allow_readonly',
      allowed_tools: ['read_file']
    }
  });
  assert.strictEqual(result.ok, false);
  assert.ok(result.reason.includes('Path outside workspace'));
});
