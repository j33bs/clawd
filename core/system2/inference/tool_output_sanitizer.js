'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const DEFAULT_MAX_CHARS = 6000;
const DEFAULT_HEAD_LINES = 60;
const DEFAULT_TAIL_LINES = 40;

function toUtcStamp(date = new Date()) {
  const iso = date.toISOString(); // 2026-03-04T01:23:45.678Z
  return iso.replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
}

function toPosInt(value, fallback) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) return fallback;
  return Math.floor(parsed);
}

function clipText(value, maxChars) {
  const text = String(value || '');
  if (text.length <= maxChars) return text;
  if (maxChars <= 16) return text.slice(0, Math.max(0, maxChars));
  return `${text.slice(0, maxChars - 13)}\n(truncated)`;
}

function safeToolName(name) {
  return String(name || 'tool')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 48) || 'tool';
}

function extractToolName(message, idx) {
  if (message && typeof message.name === 'string' && message.name.trim()) return message.name.trim();
  if (message && typeof message.tool_name === 'string' && message.tool_name.trim()) return message.tool_name.trim();
  if (message && message.metadata && typeof message.metadata.tool_name === 'string' && message.metadata.tool_name.trim()) {
    return message.metadata.tool_name.trim();
  }
  return `tool_${idx + 1}`;
}

function isToolRole(role) {
  const normalized = String(role || '').toLowerCase();
  return normalized === 'tool' || normalized === 'toolresult' || normalized === 'tool_result' || normalized === 'tool-result';
}

function contentToText(content) {
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) {
    const out = [];
    for (const part of content) {
      if (typeof part === 'string') {
        out.push(part);
      } else if (part && typeof part === 'object' && typeof part.text === 'string') {
        out.push(part.text);
      } else if (part != null) {
        out.push(JSON.stringify(part));
      }
    }
    return out.join('\n');
  }
  if (content && typeof content === 'object') {
    return JSON.stringify(content, null, 2);
  }
  if (content == null) return '';
  return String(content);
}

function detectJsonValue(content, rawText) {
  if (content && typeof content === 'object' && !Array.isArray(content)) return content;
  if (Array.isArray(content) && content.every((part) => typeof part !== 'string')) return content;
  const raw = String(rawText || '').trim();
  if (!raw || (raw[0] !== '{' && raw[0] !== '[')) return null;
  try {
    return JSON.parse(raw);
  } catch (_) {
    return null;
  }
}

function summarizeJsonScalar(value) {
  if (value == null) return null;
  const t = typeof value;
  if (t === 'string') {
    return value.length > 120 ? `${value.slice(0, 117)}...` : value;
  }
  if (t === 'number' || t === 'boolean') return value;
  if (Array.isArray(value)) return `[array:${value.length}]`;
  if (t === 'object') return `{object:${Object.keys(value).length}}`;
  return String(value);
}

function summarizeJson(value) {
  if (Array.isArray(value)) {
    return {
      type: 'array',
      item_count: value.length,
      first_items: value.slice(0, 5).map(summarizeJsonScalar)
    };
  }
  if (value && typeof value === 'object') {
    const keys = Object.keys(value);
    const sample = {};
    for (const key of keys.slice(0, 20)) {
      sample[key] = summarizeJsonScalar(value[key]);
    }
    return {
      type: 'object',
      key_count: keys.length,
      keys: keys.slice(0, 40),
      sample
    };
  }
  return {
    type: typeof value,
    value: summarizeJsonScalar(value)
  };
}

function buildPreview(rawText, options = {}) {
  const headLines = toPosInt(options.headLines, DEFAULT_HEAD_LINES);
  const tailLines = toPosInt(options.tailLines, DEFAULT_TAIL_LINES);
  const lines = String(rawText || '').split(/\r?\n/);
  const head = lines.slice(0, headLines).join('\n');
  const tail = lines.length > tailLines ? lines.slice(lines.length - tailLines).join('\n') : '';
  return {
    preview_head: head,
    preview_tail: tail,
    truncated: lines.length > (headLines + tailLines)
  };
}

function sanitizeToolOutputsForContext(messages, options = {}) {
  const env = options.env || process.env;
  if (!Array.isArray(messages) || messages.length === 0) {
    return {
      messages: Array.isArray(messages) ? messages : [],
      sanitized_count: 0,
      total_tool_output_chars: 0,
      artifacts: [],
      run_id: null
    };
  }

  const maxChars = toPosInt(env.OPENCLAW_TOOL_OUTPUT_MAX_CHARS, DEFAULT_MAX_CHARS);
  const runId = options.runId || env.OPENCLAW_RUN_ID || env.OPENCLAW_TOOL_ARTIFACT_RUN_ID || `run_${toUtcStamp()}`;
  const rootDir = path.resolve(process.cwd(), env.OPENCLAW_TOOL_ARTIFACTS_DIR || path.join('workspace', 'tool_artifacts'));
  const runDir = path.join(rootDir, runId);

  const out = [];
  const artifacts = [];
  let sanitizedCount = 0;
  let totalToolChars = 0;

  for (let idx = 0; idx < messages.length; idx++) {
    const message = messages[idx];
    if (!message || typeof message !== 'object' || !isToolRole(message.role)) {
      out.push(message);
      continue;
    }

    const raw = contentToText(message.content);
    totalToolChars += raw.length;
    sanitizedCount += 1;

    fs.mkdirSync(runDir, { recursive: true });
    const toolName = extractToolName(message, idx);
    const ts = toUtcStamp();
    const fileName = `${safeToolName(toolName)}_${ts}_${String(idx + 1).padStart(3, '0')}.txt`;
    const artifactPath = path.join(runDir, fileName);
    fs.writeFileSync(artifactPath, raw, 'utf8');

    const bytes = Buffer.byteLength(raw, 'utf8');
    const sha256 = crypto.createHash('sha256').update(raw).digest('hex');
    const preview = buildPreview(raw, options);
    const jsonValue = detectJsonValue(message.content, raw);

    const payload = {
      artifact_path: artifactPath,
      sha256,
      bytes,
      preview_head: clipText(preview.preview_head, 1800),
      preview_tail: clipText(preview.preview_tail, 1200),
      truncated: preview.truncated || raw.length > maxChars,
      tool: toolName,
      format: jsonValue !== null ? 'json' : 'text'
    };

    if (jsonValue !== null) {
      payload.summary = summarizeJson(jsonValue);
      payload.note = 'JSON tool output summarized; full content written to artifact_path.';
    } else {
      payload.note = 'Text tool output preview only; full content written to artifact_path.';
    }

    let sanitizedContent = JSON.stringify(payload);
    if (sanitizedContent.length > maxChars) {
      sanitizedContent = clipText(sanitizedContent, maxChars);
    }

    artifacts.push({
      tool: toolName,
      artifact_path: artifactPath,
      sha256,
      bytes
    });

    out.push({
      ...message,
      content: sanitizedContent
    });
  }

  return {
    messages: out,
    sanitized_count: sanitizedCount,
    total_tool_output_chars: totalToolChars,
    artifacts,
    run_id: runId
  };
}

module.exports = {
  sanitizeToolOutputsForContext,
  _test: {
    contentToText,
    detectJsonValue,
    summarizeJson,
    buildPreview,
    safeToolName,
    isToolRole
  }
};
