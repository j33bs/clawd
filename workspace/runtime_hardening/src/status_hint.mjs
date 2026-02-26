import { spawnSync } from 'node:child_process';
import fs from 'node:fs';

const DEFAULT_PORT = 8001;

function safeString(value) {
  if (typeof value === 'string') return value.trim();
  if (value == null) return '';
  return String(value).trim();
}

function isVllmLikeCommand(cmd) {
  const lowered = safeString(cmd).toLowerCase();
  if (!lowered) return false;
  return (
    lowered.includes('vllm') ||
    lowered.includes('vllm_launch_assistant') ||
    lowered.includes('openclaw-vllm')
  );
}

function parseListenerLine(stdout, port) {
  const matcher = new RegExp(`[:.]${port}\\b`);
  const lines = safeString(stdout).split(/\r?\n/);
  for (const line of lines) {
    if (!line) continue;
    if (!line.includes('LISTEN')) continue;
    if (!matcher.test(line)) continue;
    return line;
  }
  return '';
}

function parsePidFromListener(line) {
  const match = safeString(line).match(/pid=(\d+)/);
  if (!match) return undefined;
  const parsed = Number.parseInt(match[1], 10);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function parseProgramFromListener(line) {
  const match = safeString(line).match(/users:\(\("([^"]+)"/);
  return match?.[1] ? safeString(match[1]) : '';
}

function defaultRunSs() {
  const result = spawnSync('ss', ['-ltnp'], {
    encoding: 'utf8'
  });
  return {
    ok: result.status === 0,
    stdout: result.stdout || '',
    stderr: result.stderr || ''
  };
}

function readProcCmdline(pid) {
  try {
    const raw = fs.readFileSync(`/proc/${pid}/cmdline`);
    return safeString(raw.toString('utf8').replaceAll('\u0000', ' '));
  } catch {
    return '';
  }
}

export function probePortOwner(port = DEFAULT_PORT, options = {}) {
  const runSs = options.runSs || defaultRunSs;
  try {
    const result = runSs();
    if (!result || !result.ok) {
      return { port, held: false, kind: 'probe_failed' };
    }

    const listenerLine = parseListenerLine(result.stdout, port);
    if (!listenerLine) {
      return { port, held: false, kind: 'free' };
    }

    const pid = parsePidFromListener(listenerLine);
    const fallbackCmd = parseProgramFromListener(listenerLine);
    const cmd = pid ? readProcCmdline(pid) || fallbackCmd : fallbackCmd;

    if (isVllmLikeCommand(cmd)) {
      return {
        port,
        held: true,
        pid,
        cmd,
        kind: 'vllm_like'
      };
    }

    return {
      port,
      held: true,
      pid,
      cmd,
      kind: 'unknown'
    };
  } catch {
    return { port, held: false, kind: 'probe_failed' };
  }
}

export async function checkVllmHealth(options = {}) {
  const fetchImpl = options.fetchImpl || globalThis.fetch;
  const port = Number.isFinite(options.port) ? Number(options.port) : DEFAULT_PORT;
  const timeoutMs = Number.isFinite(options.timeoutMs) ? Number(options.timeoutMs) : 1200;
  if (typeof fetchImpl !== 'function') return false;

  const url = `http://127.0.0.1:${port}/health`;
  let timeoutId = null;
  try {
    const timeoutPromise = new Promise((resolve) => {
      timeoutId = setTimeout(() => resolve({ ok: false, timedOut: true }), timeoutMs);
    });
    const response = await Promise.race([fetchImpl(url), timeoutPromise]);
    return Boolean(response?.ok);
  } catch {
    return false;
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }
}

export function buildUnknownPortHint({ vllmHealthy, probe, port = DEFAULT_PORT } = {}) {
  if (vllmHealthy !== false) return null;
  if (!probe || probe.kind !== 'unknown') return null;
  const pidText = probe.pid != null ? String(probe.pid) : 'unknown';
  const cmdText = safeString(probe.cmd) || '<unknown>';
  return `HINT: vLLM blocked — port ${port} held by unknown process (pid=${pidText}, cmd="${cmdText}"). Stop it or free :${port}, then restart openclaw-vllm.service.`;
}

