'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execSync } = require('node:child_process');

const { createAuditEvent } = require('./schema');

function sha256Hex(text) {
  return crypto.createHash('sha256').update(text).digest('hex');
}

function safeExec(command, cwd) {
  try {
    return execSync(command, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim();
  } catch (_) {
    return null;
  }
}

function hashFile(filePath) {
  try {
    const raw = fs.readFileSync(filePath);
    return sha256Hex(raw);
  } catch (_) {
    return null;
  }
}

function getGitMeta(projectRoot = process.cwd()) {
  const branch = safeExec('git branch --show-current', projectRoot) || 'unknown';
  const headSha = safeExec('git rev-parse HEAD', projectRoot) || 'unknown';
  const dirty = Boolean((safeExec('git status --porcelain', projectRoot) || '').trim());
  return { branch, headSha, dirty };
}

function getConfigHashes(projectRoot = process.cwd(), env = process.env) {
  const sysConfigPath = path.join(projectRoot, 'sys', 'config.toml');
  const localOpenclawPath = path.join(projectRoot, 'openclaw.json');
  const homeOpenclawPath = path.join(os.homedir(), '.openclaw', 'openclaw.json');
  const openclawPath = fs.existsSync(localOpenclawPath) ? localOpenclawPath : homeOpenclawPath;

  return {
    sysConfigHash: hashFile(sysConfigPath),
    openclawConfigHash: hashFile(openclawPath),
    configPathHint: env.OPENCLAW_AUDIT_CONFIG_PATH || null
  };
}

function buildSnapshotEvent(options = {}) {
  const projectRoot = options.projectRoot || process.cwd();
  const runId = options.runId || crypto.randomUUID();
  const git = options.git || getGitMeta(projectRoot);
  const host = options.host || {
    platform: process.platform,
    nodeVersion: process.version
  };
  const config = options.config || getConfigHashes(projectRoot, options.env || process.env);
  const payload = {
    cwd: projectRoot,
    event: 'snapshot',
    ...options.payload
  };

  return createAuditEvent({
    ts: options.ts || Date.now(),
    eventType: 'audit.snapshot',
    runId,
    git,
    host,
    config,
    payload
  });
}

module.exports = {
  buildSnapshotEvent,
  getGitMeta,
  getConfigHashes,
  hashFile
};
