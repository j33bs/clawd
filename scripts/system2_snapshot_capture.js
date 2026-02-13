#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const DEFAULT_MAX_LOG_LINES = 500;

const COMMAND_SPECS = [
  { id: 'openclaw_version', cmd: 'openclaw', args: ['--version'], expectJson: false },
  { id: 'health', cmd: 'openclaw', args: ['health', '--json'], expectJson: true },
  { id: 'status', cmd: 'openclaw', args: ['status', '--json'], expectJson: true },
  { id: 'approvals', cmd: 'openclaw', args: ['approvals', 'get', '--json'], expectJson: true },
  { id: 'nodes', cmd: 'openclaw', args: ['nodes', 'list', '--json'], expectJson: true }
];

function parseArgs(argv) {
  const args = {
    outDir: null,
    json: false,
    maxLogLines: DEFAULT_MAX_LOG_LINES
  };

  for (let i = 0; i < argv.length; i += 1) {
    const tok = argv[i];

    if (tok === '--out' && i + 1 < argv.length) {
      args.outDir = argv[++i];
      continue;
    }

    if (tok === '--json') {
      args.json = true;
      continue;
    }

    if (tok === '--max-log-lines' && i + 1 < argv.length) {
      const parsed = Number(argv[++i]);
      if (!Number.isInteger(parsed) || parsed <= 0) {
        throw new Error('--max-log-lines must be a positive integer');
      }
      args.maxLogLines = parsed;
      continue;
    }

    throw new Error(`Unknown or incomplete argument: ${tok}`);
  }

  if (!args.outDir) {
    throw new Error('--out <dir> is required');
  }

  return args;
}

function defaultRunner(spec) {
  return spawnSync(spec.cmd, spec.args, {
    encoding: 'utf8',
    maxBuffer: 10 * 1024 * 1024
  });
}

function limitLines(text, maxLines) {
  if (!text) {
    return '';
  }
  const lines = text.split(/\r?\n/);
  return lines.slice(0, maxLines).join('\n');
}

function countPattern(text, regex) {
  const matches = text.match(regex);
  return matches ? matches.length : 0;
}

function countLogSignatures(samples) {
  const joined = samples.join('\n');
  return {
    auth_error: countPattern(joined, /\b(?:auth|unauthorized|forbidden|invalid token|bearer)\b/gi),
    module_not_found: countPattern(joined, /\bmodule[_\s-]*not[_\s-]*found\b/gi),
    quota_error: countPattern(joined, /\bquota|rate limit\b/gi),
    fetch_error: countPattern(joined, /\bfetch failed|network error|econnrefused|etimedout\b/gi),
    error_lines: countPattern(joined, /\berror\b/gi)
  };
}

function parseMaybeJson(rawText) {
  const trimmed = (rawText || '').trim();
  if (!trimmed) {
    return { ok: false, error: 'empty output' };
  }

  try {
    return { ok: true, value: JSON.parse(trimmed) };
  } catch (_) {
    // Some commands emit a short prefix line before JSON payload.
    const objectStart = trimmed.indexOf('{');
    const arrayStart = trimmed.indexOf('[');
    const starts = [objectStart, arrayStart].filter((idx) => idx >= 0).sort((a, b) => a - b);
    if (starts.length > 0) {
      const firstJsonStart = starts[0];
      const sliced = trimmed.slice(firstJsonStart);
      try {
        return { ok: true, value: JSON.parse(sliced) };
      } catch (error) {
        return { ok: false, error: error.message };
      }
    }
    return { ok: false, error: 'no JSON object/array found in output' };
  }
}

function deriveHealthOk(payload) {
  if (!payload || typeof payload !== 'object') {
    return false;
  }
  if (typeof payload.ok === 'boolean') {
    return payload.ok;
  }
  if (typeof payload.healthy === 'boolean') {
    return payload.healthy;
  }
  if (typeof payload.status === 'string') {
    return payload.status.toLowerCase() === 'ok';
  }
  return false;
}

function deriveStatusOk(payload) {
  if (!payload || typeof payload !== 'object') {
    return false;
  }
  if (typeof payload.ok === 'boolean') {
    return payload.ok;
  }
  if (typeof payload.status === 'string') {
    return payload.status.toLowerCase() === 'ok';
  }
  return true;
}

function deriveApprovalsCount(payload) {
  if (Array.isArray(payload)) {
    return payload.length;
  }
  if (!payload || typeof payload !== 'object') {
    return 0;
  }
  if (Array.isArray(payload.approvals)) {
    return payload.approvals.length;
  }
  if (Array.isArray(payload.items)) {
    return payload.items.length;
  }
  if (typeof payload.count === 'number') {
    return payload.count;
  }
  return 0;
}

function deriveNodeCounts(payload) {
  if (!payload || typeof payload !== 'object') {
    return { paired: 0, pending: 0 };
  }

  const paired = Array.isArray(payload.paired)
    ? payload.paired.length
    : Array.isArray(payload.nodes && payload.nodes.paired)
      ? payload.nodes.paired.length
      : typeof payload.paired_count === 'number'
        ? payload.paired_count
        : 0;

  const pending = Array.isArray(payload.pending)
    ? payload.pending.length
    : Array.isArray(payload.nodes && payload.nodes.pending)
      ? payload.nodes.pending.length
      : typeof payload.pending_count === 'number'
        ? payload.pending_count
        : 0;

  return { paired, pending };
}

function writeText(filePath, text) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, text, 'utf8');
}

function warnOnceFactory(warnFn) {
  let warned = false;
  return function warnOnce(msg) {
    if (warned) return;
    warned = true;
    try {
      warnFn(msg);
    } catch (_) {
      // Best-effort only: never let warnings crash snapshot capture.
    }
  };
}

function loadSystem2ObservabilityConfig(options) {
  const env = (options && options.env) || process.env;
  const explicit = options && options.system2 && options.system2.observability;

  // Precedence: explicit config > env vars > defaults.
  const enabled = explicit && typeof explicit.enabled === 'boolean'
    ? explicit.enabled
    : env.SYSTEM2_OBSERVABILITY_ENABLED === '1';

  const jsonlPath = explicit && typeof explicit.jsonlPath === 'string'
    ? explicit.jsonlPath
    : String(env.SYSTEM2_OBSERVABILITY_JSONL_PATH || '');

  const extraPayload = explicit && explicit.extraPayload && typeof explicit.extraPayload === 'object'
    ? explicit.extraPayload
    : null;

  return { enabled, jsonlPath, extraPayload };
}

function captureSnapshot(options) {
  const outDir = path.resolve(options.outDir);
  const maxLogLines = options.maxLogLines || DEFAULT_MAX_LOG_LINES;
  const runner = options.runner || defaultRunner;
  const now = options.now || (() => new Date().toISOString());
  const warnOnce = warnOnceFactory(options.warn || ((msg) => console.warn(msg)));

  fs.mkdirSync(outDir, { recursive: true });

  const summary = {
    timestamp_utc: now(),
    openclaw_version: null,
    health_ok: false,
    status_ok: false,
    approvals_count: 0,
    nodes_paired: 0,
    nodes_pending: 0,
    log_signature_counts: {
      auth_error: 0,
      module_not_found: 0,
      quota_error: 0,
      fetch_error: 0,
      error_lines: 0
    },
    commands_failed: []
  };

  const sampledLogs = [];
  const parsedPayloads = {};

  for (const spec of COMMAND_SPECS) {
    let result;
    try {
      result = runner(spec);
    } catch (error) {
      result = { status: 1, stdout: '', stderr: '', error };
    }

    const stdout = typeof result.stdout === 'string' ? result.stdout : String(result.stdout || '');
    const stderr = typeof result.stderr === 'string' ? result.stderr : String(result.stderr || '');
    const status = typeof result.status === 'number' ? result.status : 1;

    sampledLogs.push(limitLines(stdout, maxLogLines));
    sampledLogs.push(limitLines(stderr, maxLogLines));

    writeText(path.join(outDir, `${spec.id}.stdout.txt`), stdout);
    writeText(path.join(outDir, `${spec.id}.stderr.txt`), stderr);

    const meta = {
      command: [spec.cmd, ...spec.args].join(' '),
      status,
      signal: result.signal || null,
      error: result.error ? (result.error.message || String(result.error)) : null,
      parsed_json: false
    };

    if (status !== 0) {
      summary.commands_failed.push(spec.id);
    }

    if (spec.expectJson) {
      const parsed = parseMaybeJson(stdout);
      if (parsed.ok) {
        meta.parsed_json = true;
        parsedPayloads[spec.id] = parsed.value;
        writeText(path.join(outDir, `${spec.id}.json`), JSON.stringify(parsed.value, null, 2) + '\n');
      } else {
        meta.parsed_json = false;
        meta.json_error = parsed.error;
        summary.commands_failed.push(spec.id);
        writeText(path.join(outDir, `${spec.id}.json_error.txt`), parsed.error + '\n');
      }
    }

    writeText(path.join(outDir, `${spec.id}.meta.json`), JSON.stringify(meta, null, 2) + '\n');

    if (spec.id === 'openclaw_version' && status === 0) {
      summary.openclaw_version = stdout.trim().split(/\r?\n/)[0] || null;
    }
  }

  // Deduplicate failed command ids while preserving order.
  summary.commands_failed = [...new Set(summary.commands_failed)];

  if (parsedPayloads.health) {
    summary.health_ok = deriveHealthOk(parsedPayloads.health);
  }
  if (parsedPayloads.status) {
    summary.status_ok = deriveStatusOk(parsedPayloads.status);
  }
  if (parsedPayloads.approvals) {
    summary.approvals_count = deriveApprovalsCount(parsedPayloads.approvals);
  }
  if (parsedPayloads.nodes) {
    const counts = deriveNodeCounts(parsedPayloads.nodes);
    summary.nodes_paired = counts.paired;
    summary.nodes_pending = counts.pending;
  }

  summary.log_signature_counts = countLogSignatures(sampledLogs);

  writeText(path.join(outDir, 'snapshot_summary.json'), JSON.stringify(summary, null, 2) + '\n');

  // Phase-3 seam: System-2 observability emission (default-off).
  // Must not affect behavior unless explicitly enabled.
  try {
    const obs = loadSystem2ObservabilityConfig(options);
    if (obs.enabled === true) {
      if (typeof obs.jsonlPath !== 'string' || obs.jsonlPath.trim().length === 0) {
        warnOnce('system2 observability enabled but jsonl path is missing; disabling emission');
      } else {
        const parentDir = path.dirname(obs.jsonlPath);
        let parentOk = false;
        try {
          parentOk = fs.existsSync(parentDir) && fs.statSync(parentDir).isDirectory();
        } catch (_) {
          parentOk = false;
        }
        if (!parentOk) {
          warnOnce('system2 observability enabled but jsonl parent directory is missing; disabling emission');
        } else {
          const { appendEventJsonl } = require('../core/system2/observability/jsonl_sink');
          const { deepRedact } = require('../core/system2/observability/redaction');

          const payload = Object.assign(
            {
              snapshot_ok: summary.commands_failed.length === 0,
              commands_failed: summary.commands_failed,
              log_signature_counts: summary.log_signature_counts
            },
            obs.extraPayload || {}
          );

          const event = {
            type: 'system2_event_v1',
            version: '1',
            ts_utc: summary.timestamp_utc,
            event_type: 'system2_snapshot_captured',
            level: 'info',
            payload: deepRedact(payload || {}, 'payload'),
            context: { subsystem: 'system2_snapshot_capture' }
          };

          fs.appendFileSync(obs.jsonlPath, appendEventJsonl(event), 'utf8');
        }
      }
    }
  } catch (error) {
    warnOnce(`system2 observability emit failed: ${error.message}`);
  }

  return {
    ok: summary.commands_failed.length === 0,
    outDir,
    summary
  };
}

function main() {
  let args;

  try {
    args = parseArgs(process.argv.slice(2));
  } catch (error) {
    console.error(error.message);
    process.exit(2);
  }

  const result = captureSnapshot(args);

  if (args.json) {
    console.log(JSON.stringify(result.summary, null, 2));
  } else {
    console.log(
      `snapshot: health_ok=${result.summary.health_ok} status_ok=${result.summary.status_ok} approvals=${result.summary.approvals_count} nodes=${result.summary.nodes_paired}/${result.summary.nodes_pending}`
    );
  }

  if (!result.ok) {
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = {
  COMMAND_SPECS,
  DEFAULT_MAX_LOG_LINES,
  captureSnapshot,
  countLogSignatures,
  parseArgs
};
