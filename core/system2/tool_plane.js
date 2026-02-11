'use strict';

const fs = require('node:fs');
const path = require('node:path');

const { redactValue } = require('../../sys/audit/redaction');

function nowIso() {
  return new Date().toISOString();
}

class System2ToolPlane {
  constructor(options = {}) {
    this.workspaceRoot = options.workspaceRoot || process.cwd();
    this.allowlistPath =
      options.allowlistPath ||
      path.join(this.workspaceRoot, 'core', 'system2', 'tool_allowlist.readonly.json');
    this.artifactDir =
      options.artifactDir ||
      path.join(this.workspaceRoot, 'sys', 'state', 'system2', 'tool_artifacts');
    this.onEvent = typeof options.onEvent === 'function' ? options.onEvent : null;
  }

  loadAllowlist() {
    const raw = fs.readFileSync(this.allowlistPath, 'utf8');
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || !Array.isArray(parsed.tools)) {
      throw new Error('Invalid tool allowlist');
    }
    return parsed;
  }

  isAllowedTool(toolName, policy = {}, allowlist = null) {
    const loaded = allowlist || this.loadAllowlist();
    if (!policy || policy.mode === 'deny') {
      return false;
    }
    if (Array.isArray(policy.allowed_tools) && policy.allowed_tools.length > 0) {
      return policy.allowed_tools.includes(toolName);
    }
    return loaded.tools.some((entry) => entry && entry.name === toolName && entry.read_only === true);
  }

  emitEvent(event) {
    if (!this.onEvent) {
      return;
    }
    this.onEvent({
      ts: nowIso(),
      ...event
    });
  }

  resolveWorkspacePath(inputPath) {
    const target = String(inputPath || '').trim();
    const absolute = path.isAbsolute(target)
      ? path.resolve(target)
      : path.resolve(this.workspaceRoot, target || '.');
    const prefix = `${this.workspaceRoot}${path.sep}`;
    if (absolute === this.workspaceRoot || absolute.startsWith(prefix)) {
      return absolute;
    }
    return null;
  }

  writeArtifact(toolName, payload) {
    fs.mkdirSync(this.artifactDir, { recursive: true });
    const fileName = `${Date.now()}-${toolName}.json`;
    const artifactPath = path.join(this.artifactDir, fileName);
    fs.writeFileSync(artifactPath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
    return artifactPath;
  }

  listDir(args = {}) {
    const relativePath = String(args.path || '.');
    const absolutePath = this.resolveWorkspacePath(relativePath);
    if (!absolutePath || !absolutePath.startsWith(this.workspaceRoot)) {
      throw new Error('Path outside workspace');
    }
    const entries = fs.readdirSync(absolutePath).sort();
    return {
      path: absolutePath,
      entries
    };
  }

  readFile(args = {}) {
    const relativePath = String(args.path || '').trim();
    if (!relativePath) {
      throw new Error('Missing file path');
    }
    const absolutePath = this.resolveWorkspacePath(relativePath);
    if (!absolutePath || !absolutePath.startsWith(this.workspaceRoot)) {
      throw new Error('Path outside workspace');
    }
    const maxBytes = Number(args.max_bytes || 8192);
    const buffer = fs.readFileSync(absolutePath);
    const slice = buffer.subarray(0, Math.max(1, maxBytes));
    return {
      path: absolutePath,
      truncated: buffer.length > slice.length,
      content: slice.toString('utf8')
    };
  }

  executeToolCall({ tool, args = {}, policy = {} } = {}) {
    const toolName = String(tool || '').trim();
    if (!toolName) {
      return {
        ok: false,
        reason: 'missing_tool',
        artifactRef: null,
        redactedOutput: null
      };
    }

    const allowlist = this.loadAllowlist();
    if (!this.isAllowedTool(toolName, policy, allowlist)) {
      this.emitEvent({
        event_type: 'tool_call',
        tool: toolName,
        status: 'denied',
        reason: 'tool_not_allowlisted'
      });
      return {
        ok: false,
        reason: 'tool_not_allowlisted',
        artifactRef: null,
        redactedOutput: null
      };
    }

    try {
      let output;
      if (toolName === 'list_dir') {
        output = this.listDir(args);
      } else if (toolName === 'read_file') {
        output = this.readFile(args);
      } else {
        return {
          ok: false,
          reason: 'tool_not_implemented',
          artifactRef: null,
          redactedOutput: null
        };
      }

      const redactedOutput = redactValue(output);
      const artifactRef = this.writeArtifact(toolName, {
        tool: toolName,
        args,
        redactedOutput
      });

      this.emitEvent({
        event_type: 'tool_call',
        tool: toolName,
        status: 'ok',
        artifact_ref: artifactRef
      });
      this.emitEvent({
        event_type: 'artifact_write',
        tool: toolName,
        artifact_ref: artifactRef
      });

      return {
        ok: true,
        reason: null,
        artifactRef,
        redactedOutput
      };
    } catch (error) {
      this.emitEvent({
        event_type: 'tool_call',
        tool: toolName,
        status: 'error',
        reason: error && error.message ? error.message : String(error)
      });
      return {
        ok: false,
        reason: error && error.message ? error.message : String(error),
        artifactRef: null,
        redactedOutput: null
      };
    }
  }
}

module.exports = {
  System2ToolPlane
};
