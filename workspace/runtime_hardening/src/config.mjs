import path from 'node:path';
import { isPathWithinRoot } from './security/fs_sandbox.mjs';

const NODE_ENVS = new Set(['development', 'test', 'production']);

const DEFAULTS = Object.freeze({
  nodeEnv: 'development',
  sessionTtlMs: 6 * 60 * 60 * 1000,
  sessionMax: 50,
  historyMaxMessages: 200,
  mcpServerStartTimeoutMs: 30_000,
  logLevel: 'info',
  fsAllowOutsideWorkspace: false
});

let configCache = null;

function parseBoolean(value, fallback = false) {
  if (value == null || value === '') return fallback;
  const normalized = String(value).trim().toLowerCase();
  if (['1', 'true', 'yes', 'on'].includes(normalized)) return true;
  if (['0', 'false', 'no', 'off'].includes(normalized)) return false;
  return fallback;
}

function parsePositiveInt(field, rawValue, fallback, errors) {
  if (rawValue == null || rawValue === '') return fallback;
  const parsed = Number(rawValue);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    errors.push(`${field}: must be a positive integer`);
    return fallback;
  }
  return parsed;
}

function resolveWorkspacePath(value, workspaceRoot) {
  if (!value || typeof value !== 'string') return workspaceRoot;
  return path.isAbsolute(value) ? path.resolve(value) : path.resolve(workspaceRoot, value);
}

function validateConfig(env = process.env) {
  const errors = [];

  const anthropicApiKey = typeof env.ANTHROPIC_API_KEY === 'string' ? env.ANTHROPIC_API_KEY.trim() : '';
  if (!anthropicApiKey) {
    errors.push('ANTHROPIC_API_KEY: required non-empty value is missing');
  }

  const nodeEnv = typeof env.NODE_ENV === 'string' && env.NODE_ENV.trim() ? env.NODE_ENV.trim() : DEFAULTS.nodeEnv;
  if (!NODE_ENVS.has(nodeEnv)) {
    errors.push(`NODE_ENV: must be one of development|test|production (received "${nodeEnv}")`);
  }

  const workspaceRoot = resolveWorkspacePath(env.WORKSPACE_ROOT || process.cwd(), process.cwd());
  const fsAllowOutsideWorkspace = parseBoolean(env.FS_ALLOW_OUTSIDE_WORKSPACE, DEFAULTS.fsAllowOutsideWorkspace);
  const agentWorkspaceRoot = resolveWorkspacePath(
    env.AGENT_WORKSPACE_ROOT || path.join(workspaceRoot, '.agent_workspace'),
    workspaceRoot
  );
  const skillsRoot = resolveWorkspacePath(env.SKILLS_ROOT || path.join(workspaceRoot, 'skills'), workspaceRoot);

  if (!fsAllowOutsideWorkspace) {
    try {
      if (!isPathWithinRoot(workspaceRoot, agentWorkspaceRoot)) {
        errors.push('AGENT_WORKSPACE_ROOT: must stay within WORKSPACE_ROOT by default');
      }
      if (!isPathWithinRoot(workspaceRoot, skillsRoot)) {
        errors.push('SKILLS_ROOT: must stay within WORKSPACE_ROOT by default');
      }
    } catch (error) {
      errors.push(`WORKSPACE_ROOT: ${error.message}`);
    }
  }

  const sessionTtlMs = parsePositiveInt('SESSION_TTL_MS', env.SESSION_TTL_MS, DEFAULTS.sessionTtlMs, errors);
  const sessionMax = parsePositiveInt('SESSION_MAX', env.SESSION_MAX, DEFAULTS.sessionMax, errors);
  const historyMaxMessages = parsePositiveInt(
    'HISTORY_MAX_MESSAGES',
    env.HISTORY_MAX_MESSAGES,
    DEFAULTS.historyMaxMessages,
    errors
  );
  const mcpServerStartTimeoutMs = parsePositiveInt(
    'MCP_SERVER_START_TIMEOUT_MS',
    env.MCP_SERVER_START_TIMEOUT_MS,
    DEFAULTS.mcpServerStartTimeoutMs,
    errors
  );

  if (errors.length > 0) {
    throw new Error(`Invalid runtime hardening configuration:\n- ${errors.join('\n- ')}`);
  }

  return {
    anthropicApiKey,
    nodeEnv,
    workspaceRoot,
    agentWorkspaceRoot,
    skillsRoot,
    sessionTtlMs,
    sessionMax,
    historyMaxMessages,
    mcpServerStartTimeoutMs,
    logLevel: typeof env.LOG_LEVEL === 'string' && env.LOG_LEVEL.trim() ? env.LOG_LEVEL.trim() : DEFAULTS.logLevel,
    fsAllowOutsideWorkspace
  };
}

function getConfig(env = process.env) {
  if (configCache) return configCache;
  configCache = validateConfig(env);
  return configCache;
}

function clearConfigCache() {
  configCache = null;
}

function redactConfigForLogs(config) {
  return {
    ...config,
    anthropicApiKey: config?.anthropicApiKey ? '<redacted>' : '<missing>'
  };
}

export { DEFAULTS, clearConfigCache, getConfig, redactConfigForLogs, validateConfig };
