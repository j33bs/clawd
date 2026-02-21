'use strict';

/**
 * FreeComputeCloud — Secrets Bridge
 *
 * Persist provider API keys in OS-native secret stores, then inject them into
 * the current process environment at runtime when ENABLE_SECRETS_BRIDGE=1.
 *
 * Safety:
 * - Never logs secret values.
 * - Never mutates global/system environment outside the current process.
 * - Operator-provided env vars always override stored secrets.
 */

const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const { getProvider } = require('./catalog');
const { ProviderAdapter } = require('./provider_adapter');

const PROVIDER_ENV_MAP = Object.freeze({
  groq: Object.freeze({
    envVar: 'OPENCLAW_GROQ_API_KEY',
    aliasEnvVars: ['GROQ_API_KEY'],
    baseUrlEnvVar: 'OPENCLAW_GROQ_BASE_URL',
    catalogProviderId: 'groq'
  }),
  gemini: Object.freeze({
    envVar: 'OPENCLAW_GEMINI_API_KEY',
    baseUrlEnvVar: 'OPENCLAW_GEMINI_BASE_URL',
    catalogProviderId: 'gemini'
  }),
  openrouter: Object.freeze({
    envVar: 'OPENCLAW_OPENROUTER_API_KEY',
    baseUrlEnvVar: 'OPENCLAW_OPENROUTER_BASE_URL',
    catalogProviderId: 'openrouter'
  }),
  'minimax-portal': Object.freeze({
    envVar: 'OPENCLAW_MINIMAX_PORTAL_API_KEY',
    baseUrlEnvVar: 'OPENCLAW_MINIMAX_PORTAL_BASE_URL',
    catalogProviderId: 'minimax-portal'
  }),
  qwen: Object.freeze({
    envVar: 'OPENCLAW_QWEN_API_KEY',
    baseUrlEnvVar: 'OPENCLAW_QWEN_BASE_URL',
    catalogProviderId: 'qwen_alibaba'
  }),
  vllm: Object.freeze({
    envVar: 'OPENCLAW_VLLM_API_KEY',
    baseUrlEnvVar: 'OPENCLAW_VLLM_BASE_URL',
    catalogProviderId: 'local_vllm'
  })
});

const BACKEND_TYPES = Object.freeze({
  AUTO: 'auto',
  KEYCHAIN: 'keychain',
  CREDMAN: 'credman',
  SECRETSERVICE: 'secretservice',
  FILE: 'file'
});

const DEFAULT_SECRETS_FILE = '.openclaw/secrets.enc';

function normalizeProviderId(providerId) {
  const key = String(providerId || '').trim().toLowerCase();
  if (key === 'qwen_alibaba') {
    return 'qwen';
  }
  if (key === 'minimax_portal') {
    return 'minimax-portal';
  }
  return key;
}

function maskSecretFingerprint(secretValue) {
  const value = String(secretValue || '');
  const hashPrefix = crypto.createHash('sha256').update(value).digest('hex').slice(0, 12);
  const tail = value.slice(-4);
  return `${hashPrefix}…${tail}`;
}

function parseBoolFlag(value, defaultValue) {
  if (value === '1') return true;
  if (value === '0') return false;
  return defaultValue;
}

class SecretsBridge {
  constructor(options = {}) {
    const env = options.env || process.env;
    const platform = options.platform || process.platform;

    Object.defineProperty(this, '_env', {
      value: env,
      writable: false,
      enumerable: false
    });
    Object.defineProperty(this, '_platform', {
      value: platform,
      writable: false,
      enumerable: false
    });
    Object.defineProperty(this, '_spawnSync', {
      value: options.spawnSync || spawnSync,
      writable: false,
      enumerable: false
    });
    Object.defineProperty(this, '_fs', {
      value: options.fs || fs,
      writable: false,
      enumerable: false
    });
    Object.defineProperty(this, '_path', {
      value: options.path || path,
      writable: false,
      enumerable: false
    });
    Object.defineProperty(this, '_os', {
      value: options.os || os,
      writable: false,
      enumerable: false
    });
    Object.defineProperty(this, '_backendAdapter', {
      value: options.backendAdapter || null,
      writable: false,
      enumerable: false
    });
    Object.defineProperty(this, '_testProbeFn', {
      value: options.testProbeFn || null,
      writable: false,
      enumerable: false
    });

    this.config = Object.freeze({
      enabled: parseBoolFlag(env.ENABLE_SECRETS_BRIDGE, false),
      backend: String(env.SECRETS_BACKEND || BACKEND_TYPES.AUTO).toLowerCase(),
      allowUiIntake: parseBoolFlag(env.SECRETS_ALLOW_UI_INTAKE, false),
      uiLocalhostOnly: parseBoolFlag(env.SECRETS_UI_LOCALHOST_ONLY, true),
      secretsFilePath: options.secretsFilePath || this._path.join(this._os.homedir(), DEFAULT_SECRETS_FILE)
    });
  }

  static providerMap() {
    return PROVIDER_ENV_MAP;
  }

  static backendTypes() {
    return BACKEND_TYPES;
  }

  static maskSecretFingerprint(secretValue) {
    return maskSecretFingerprint(secretValue);
  }

  normalizeProvider(providerId) {
    const normalized = normalizeProviderId(providerId);
    const mapping = PROVIDER_ENV_MAP[normalized];
    if (!mapping) {
      throw new Error(`unsupported provider: ${providerId}`);
    }
    return {
      providerId: normalized,
      ...mapping
    };
  }

  detectBackend() {
    if (this.config.backend && this.config.backend !== BACKEND_TYPES.AUTO) {
      if (!Object.values(BACKEND_TYPES).includes(this.config.backend)) {
        throw new Error(`unsupported secrets backend: ${this.config.backend}`);
      }
      return this.config.backend;
    }

    if (this._platform === 'darwin') {
      return BACKEND_TYPES.KEYCHAIN;
    }
    if (this._platform === 'win32') {
      return BACKEND_TYPES.CREDMAN;
    }
    if (this._platform === 'linux') {
      return BACKEND_TYPES.SECRETSERVICE;
    }
    return BACKEND_TYPES.FILE;
  }

  status() {
    const backend = this.detectBackend();
    const rows = [];
    for (const providerId of Object.keys(PROVIDER_ENV_MAP)) {
      const mapping = this.normalizeProvider(providerId);
      let stored = false;
      let backendError = null;
      try {
        stored = !!this._readSecret(mapping.providerId, { backend });
      } catch (error) {
        backendError = error.message;
      }
      rows.push({
        provider: mapping.providerId,
        envVar: mapping.envVar,
        baseUrlEnvVar: mapping.baseUrlEnvVar,
        present: stored,
        injectedFromEnv: !!this._env[mapping.envVar],
        backend,
        backendError
      });
    }
    return rows;
  }

  setSecret(providerId, secretValue, options = {}) {
    const mapping = this.normalizeProvider(providerId);
    const secret = String(secretValue || '');
    if (!secret) {
      throw new Error('secret must be non-empty');
    }
    const backend = this.detectBackend();
    this._writeSecret(mapping.providerId, secret, { backend, passphrase: options.passphrase });
    return {
      provider: mapping.providerId,
      envVar: mapping.envVar,
      backend,
      fingerprint: maskSecretFingerprint(secret)
    };
  }

  unsetSecret(providerId, options = {}) {
    const mapping = this.normalizeProvider(providerId);
    const backend = this.detectBackend();
    this._deleteSecret(mapping.providerId, { backend, passphrase: options.passphrase });
    return {
      provider: mapping.providerId,
      envVar: mapping.envVar,
      backend,
      removed: true
    };
  }

  injectRuntimeEnv(targetEnv, options = {}) {
    if (!this.config.enabled) {
      return {
        enabled: false,
        backend: this.detectBackend(),
        injected: [],
        skipped: []
      };
    }

    const env = targetEnv || this._env;
    const backend = this.detectBackend();
    const providers = Array.isArray(options.providers) && options.providers.length > 0
      ? options.providers.map((provider) => normalizeProviderId(provider))
      : Object.keys(PROVIDER_ENV_MAP);

    const injected = [];
    const skipped = [];

    for (const providerId of providers) {
      const mapping = this.normalizeProvider(providerId);
      const envVars = [mapping.envVar, ...(mapping.aliasEnvVars || [])];
      const existing = envVars.map((k) => env[k]).find((v) => !!v);
      if (existing) {
        // Operator override wins, but we still propagate to missing aliases to avoid drift.
        for (const k of envVars) {
          if (!env[k]) {
            env[k] = existing;
            injected.push({ provider: mapping.providerId, envVar: k });
          }
        }
        skipped.push({ provider: mapping.providerId, envVar: mapping.envVar, reason: 'operator_override' });
        continue;
      }

      const secret = this._readSecret(mapping.providerId, { backend, passphrase: options.passphrase });
      if (!secret) {
        skipped.push({
          provider: mapping.providerId,
          envVar: mapping.envVar,
          reason: 'missing'
        });
        continue;
      }

      for (const k of envVars) {
        env[k] = secret;
        injected.push({ provider: mapping.providerId, envVar: k });
      }
    }

    return {
      enabled: true,
      backend,
      injected,
      skipped
    };
  }

  async testProvider(providerId, options = {}) {
    const mapping = this.normalizeProvider(providerId);

    if (typeof this._testProbeFn === 'function') {
      return this._testProbeFn(mapping.providerId, options);
    }

    const env = { ...this._env };
    const injection = this.injectRuntimeEnv(env, {
      providers: [mapping.providerId],
      passphrase: options.passphrase
    });

    if (!env[mapping.envVar]) {
      return {
        provider: mapping.providerId,
        ok: false,
        code: 'missing_secret',
        injection
      };
    }

    const entry = getProvider(mapping.catalogProviderId);
    if (!entry) {
      return {
        provider: mapping.providerId,
        ok: false,
        code: 'provider_not_found'
      };
    }

    try {
      const adapter = new ProviderAdapter(entry, { env });
      const health = await adapter.health();
      return {
        provider: mapping.providerId,
        ok: !!health.ok,
        code: health.ok ? 'ok' : 'probe_failed'
      };
    } catch (error) {
      return {
        provider: mapping.providerId,
        ok: false,
        code: 'probe_exception'
      };
    }
  }

  _writeSecret(providerId, secretValue, options = {}) {
    if (this._backendAdapter && typeof this._backendAdapter.set === 'function') {
      this._backendAdapter.set(providerId, secretValue, options);
      return;
    }

    const backend = options.backend;
    if (backend === BACKEND_TYPES.KEYCHAIN) {
      this._writeMacKeychain(providerId, secretValue);
      return;
    }
    if (backend === BACKEND_TYPES.CREDMAN) {
      this._writeWindowsCredman(providerId, secretValue);
      return;
    }
    if (backend === BACKEND_TYPES.SECRETSERVICE) {
      this._writeLinuxSecretService(providerId, secretValue);
      return;
    }
    if (backend === BACKEND_TYPES.FILE) {
      this._assertFileBackendOptIn();
      const passphrase = this._resolveFileBackendPassphrase({ passphrase: options.passphrase });
      this._writeFileSecret(providerId, secretValue, passphrase);
      return;
    }
    throw new Error(`unsupported backend: ${backend}`);
  }

  _readSecret(providerId, options = {}) {
    if (this._backendAdapter && typeof this._backendAdapter.get === 'function') {
      return this._backendAdapter.get(providerId, options) || null;
    }

    const backend = options.backend;
    if (backend === BACKEND_TYPES.KEYCHAIN) {
      return this._readMacKeychain(providerId);
    }
    if (backend === BACKEND_TYPES.CREDMAN) {
      return this._readWindowsCredman(providerId);
    }
    if (backend === BACKEND_TYPES.SECRETSERVICE) {
      return this._readLinuxSecretService(providerId);
    }
    if (backend === BACKEND_TYPES.FILE) {
      this._assertFileBackendOptIn();
      const passphrase = this._resolveFileBackendPassphrase({ passphrase: options.passphrase });
      return this._readFileSecret(providerId, passphrase);
    }
    throw new Error(`unsupported backend: ${backend}`);
  }

  _deleteSecret(providerId, options = {}) {
    if (this._backendAdapter && typeof this._backendAdapter.unset === 'function') {
      this._backendAdapter.unset(providerId, options);
      return;
    }

    const backend = options.backend;
    if (backend === BACKEND_TYPES.KEYCHAIN) {
      this._deleteMacKeychain(providerId);
      return;
    }
    if (backend === BACKEND_TYPES.CREDMAN) {
      this._deleteWindowsCredman(providerId);
      return;
    }
    if (backend === BACKEND_TYPES.SECRETSERVICE) {
      this._deleteLinuxSecretService(providerId);
      return;
    }
    if (backend === BACKEND_TYPES.FILE) {
      this._assertFileBackendOptIn();
      const passphrase = this._resolveFileBackendPassphrase({ passphrase: options.passphrase });
      this._deleteFileSecret(providerId, passphrase);
      return;
    }
    throw new Error(`unsupported backend: ${backend}`);
  }

  _runCommand(command, args, options = {}) {
    const result = this._spawnSync(command, args, {
      encoding: 'utf8',
      input: options.input || null,
      env: options.env || this._env
    });

    const code = typeof result.status === 'number' ? result.status : 1;
    if (code !== 0) {
      const tail = String(result.stderr || '')
        .split(/\r?\n/)
        .filter(Boolean)
        .slice(-1)[0] || `${command} exited ${code}`;
      const err = new Error(tail);
      err.exitCode = code;
      throw err;
    }

    return String(result.stdout || '');
  }

  _serviceName(providerId) {
    return `openclaw/${providerId}/api_key`;
  }

  _writeMacKeychain(providerId, secretValue) {
    if (this._platform !== 'darwin') {
      throw new Error('keychain backend requires macOS');
    }

    const user = this._env.USER || this._env.LOGNAME || 'openclaw';
    this._runCommand('security', [
      'add-generic-password',
      '-a', user,
      '-s', this._serviceName(providerId),
      '-w', secretValue,
      '-U'
    ]);
  }

  _readMacKeychain(providerId) {
    if (this._platform !== 'darwin') {
      throw new Error('keychain backend requires macOS');
    }

    const user = this._env.USER || this._env.LOGNAME || 'openclaw';
    try {
      return this._runCommand('security', [
        'find-generic-password',
        '-a', user,
        '-s', this._serviceName(providerId),
        '-w'
      ]).trim();
    } catch (error) {
      if (/could not be found/i.test(error.message)) {
        return null;
      }
      throw error;
    }
  }

  _deleteMacKeychain(providerId) {
    if (this._platform !== 'darwin') {
      throw new Error('keychain backend requires macOS');
    }

    const user = this._env.USER || this._env.LOGNAME || 'openclaw';
    try {
      this._runCommand('security', [
        'delete-generic-password',
        '-a', user,
        '-s', this._serviceName(providerId)
      ]);
    } catch (error) {
      if (/could not be found/i.test(error.message)) {
        return;
      }
      throw error;
    }
  }

  _writeWindowsCredman(providerId, secretValue) {
    if (this._platform !== 'win32') {
      throw new Error('credman backend requires Windows');
    }
    const script = [
      '$ErrorActionPreference = "Stop"',
      'if (-not (Get-Module -ListAvailable -Name CredentialManager)) { exit 42 }',
      'Import-Module CredentialManager',
      '$user = if ($env:USERNAME) { $env:USERNAME } else { "openclaw" }',
      '$secure = ConvertTo-SecureString $env:OPENCLAW_SECRET_VALUE -AsPlainText -Force',
      `New-StoredCredential -Target "${this._serviceName(providerId)}" -UserName $user -Password $secure -Persist LocalMachine | Out-Null`
    ].join('; ');

    try {
      this._runCommand('powershell', ['-NoProfile', '-Command', script], {
        env: {
          ...this._env,
          OPENCLAW_SECRET_VALUE: secretValue
        }
      });
    } catch (error) {
      if (error.exitCode === 42) {
        throw new Error('CredentialManager module missing; set SECRETS_BACKEND=file for explicit fallback');
      }
      throw error;
    }
  }

  _readWindowsCredman(providerId) {
    if (this._platform !== 'win32') {
      throw new Error('credman backend requires Windows');
    }
    const script = [
      '$ErrorActionPreference = "Stop"',
      'if (-not (Get-Module -ListAvailable -Name CredentialManager)) { exit 42 }',
      'Import-Module CredentialManager',
      `$cred = Get-StoredCredential -Target "${this._serviceName(providerId)}"`,
      'if ($null -eq $cred) { exit 44 }',
      '$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($cred.Password)',
      '[Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)'
    ].join('; ');

    try {
      return this._runCommand('powershell', ['-NoProfile', '-Command', script]).trim() || null;
    } catch (error) {
      if (error.exitCode === 42) {
        throw new Error('CredentialManager module missing; set SECRETS_BACKEND=file for explicit fallback');
      }
      if (error.exitCode === 44) {
        return null;
      }
      throw error;
    }
  }

  _deleteWindowsCredman(providerId) {
    if (this._platform !== 'win32') {
      throw new Error('credman backend requires Windows');
    }
    const script = [
      '$ErrorActionPreference = "Stop"',
      'if (-not (Get-Module -ListAvailable -Name CredentialManager)) { exit 42 }',
      'Import-Module CredentialManager',
      `$cred = Get-StoredCredential -Target "${this._serviceName(providerId)}"`,
      'if ($null -eq $cred) { exit 44 }',
      `Remove-StoredCredential -Target "${this._serviceName(providerId)}" | Out-Null`
    ].join('; ');

    try {
      this._runCommand('powershell', ['-NoProfile', '-Command', script]);
    } catch (error) {
      if (error.exitCode === 44) {
        return;
      }
      if (error.exitCode === 42) {
        throw new Error('CredentialManager module missing; set SECRETS_BACKEND=file for explicit fallback');
      }
      throw error;
    }
  }

  _writeLinuxSecretService(providerId, secretValue) {
    if (this._platform !== 'linux') {
      throw new Error('secretservice backend requires Linux');
    }
    this._runCommand(
      'secret-tool',
      ['store', '--label', `OpenClaw ${providerId} API key`, 'service', 'openclaw', 'provider', providerId, 'type', 'api_key'],
      { input: secretValue }
    );
  }

  _readLinuxSecretService(providerId) {
    if (this._platform !== 'linux') {
      throw new Error('secretservice backend requires Linux');
    }

    try {
      return this._runCommand(
        'secret-tool',
        ['lookup', 'service', 'openclaw', 'provider', providerId, 'type', 'api_key']
      ).trim() || null;
    } catch (error) {
      if (/No such secret collection|not found/i.test(error.message)) {
        return null;
      }
      throw error;
    }
  }

  _deleteLinuxSecretService(providerId) {
    if (this._platform !== 'linux') {
      throw new Error('secretservice backend requires Linux');
    }

    try {
      this._runCommand(
        'secret-tool',
        ['clear', 'service', 'openclaw', 'provider', providerId, 'type', 'api_key']
      );
    } catch (error) {
      if (/No such secret collection|not found/i.test(error.message)) {
        return;
      }
      throw error;
    }
  }

  _assertFileBackendOptIn() {
    if (this.config.backend !== BACKEND_TYPES.FILE) {
      throw new Error('file backend requires explicit opt-in (SECRETS_BACKEND=file)');
    }
  }

  _isDevRuntime() {
    const openclawEnv = String(this._env.OPENCLAW_ENV || '').trim().toLowerCase();
    const nodeEnv = String(this._env.NODE_ENV || '').trim().toLowerCase();
    return openclawEnv === 'dev'
      || openclawEnv === 'development'
      || openclawEnv === 'test'
      || nodeEnv === 'development'
      || nodeEnv === 'test';
  }

  _readPassphraseFile(passphraseFilePath) {
    const filePath = this._path.resolve(String(passphraseFilePath || ''));
    if (!filePath) return null;

    let st;
    try {
      st = this._fs.statSync(filePath);
    } catch (_) {
      throw new Error(`passphrase file not readable: ${filePath}`);
    }
    if (!st.isFile()) {
      throw new Error(`passphrase file must be a regular file: ${filePath}`);
    }
    if (process.platform !== 'win32') {
      const mode = st.mode & 0o777;
      if ((mode & 0o077) !== 0) {
        throw new Error(`passphrase file permissions too open (require 0600): ${filePath}`);
      }
    }

    const value = String(this._fs.readFileSync(filePath, 'utf8') || '').trim();
    if (!value) {
      throw new Error(`passphrase file is empty: ${filePath}`);
    }
    return value;
  }

  _resolveFileBackendPassphrase(options = {}) {
    if (options.passphrase) {
      return String(options.passphrase);
    }

    const passphraseFile = this._env.SECRETS_FILE_PASSPHRASE_FILE;
    if (passphraseFile) {
      return this._readPassphraseFile(passphraseFile);
    }

    const envPassphrase = this._env.SECRETS_FILE_PASSPHRASE;
    if (envPassphrase) {
      const allowEnvPassphrase = parseBoolFlag(this._env.SECRETS_ALLOW_ENV_PASSPHRASE, false)
        || this._isDevRuntime();
      if (!allowEnvPassphrase) {
        throw new Error(
          'SECRETS_FILE_PASSPHRASE is blocked outside development/test; use SECRETS_FILE_PASSPHRASE_FILE'
        );
      }
      return envPassphrase;
    }

    return null;
  }

  _readFilePayload(passphrase) {
    if (!passphrase) {
      throw new Error('file backend requires passphrase');
    }

    const filePath = this.config.secretsFilePath;
    if (!this._fs.existsSync(filePath)) {
      return {};
    }
    const raw = this._fs.readFileSync(filePath, 'utf8');
    const payload = JSON.parse(raw);

    const salt = Buffer.from(payload.salt, 'base64');
    const iv = Buffer.from(payload.iv, 'base64');
    const tag = Buffer.from(payload.tag, 'base64');
    const ciphertext = Buffer.from(payload.ciphertext, 'base64');

    const key = crypto.pbkdf2Sync(passphrase, salt, 310000, 32, 'sha256');
    const decipher = crypto.createDecipheriv('aes-256-gcm', key, iv);
    decipher.setAuthTag(tag);
    const clear = Buffer.concat([
      decipher.update(ciphertext),
      decipher.final()
    ]);
    const parsed = JSON.parse(clear.toString('utf8'));
    return parsed && typeof parsed === 'object' ? parsed : {};
  }

  _writeFilePayload(map, passphrase) {
    if (!passphrase) {
      throw new Error('file backend requires passphrase');
    }
    const clear = Buffer.from(JSON.stringify(map), 'utf8');
    const salt = crypto.randomBytes(16);
    const iv = crypto.randomBytes(12);
    const key = crypto.pbkdf2Sync(passphrase, salt, 310000, 32, 'sha256');
    const cipher = crypto.createCipheriv('aes-256-gcm', key, iv);
    const ciphertext = Buffer.concat([cipher.update(clear), cipher.final()]);
    const tag = cipher.getAuthTag();

    const payload = {
      version: 1,
      kdf: 'pbkdf2-sha256',
      iterations: 310000,
      salt: salt.toString('base64'),
      iv: iv.toString('base64'),
      tag: tag.toString('base64'),
      ciphertext: ciphertext.toString('base64')
    };

    const filePath = this.config.secretsFilePath;
    this._fs.mkdirSync(this._path.dirname(filePath), { recursive: true });
    this._fs.writeFileSync(filePath, JSON.stringify(payload, null, 2) + '\n', { mode: 0o600 });
  }

  _writeFileSecret(providerId, secretValue, passphrase) {
    const map = this._readFilePayload(passphrase);
    map[providerId] = secretValue;
    this._writeFilePayload(map, passphrase);
  }

  _readFileSecret(providerId, passphrase) {
    const map = this._readFilePayload(passphrase);
    return map[providerId] || null;
  }

  _deleteFileSecret(providerId, passphrase) {
    const map = this._readFilePayload(passphrase);
    if (!Object.prototype.hasOwnProperty.call(map, providerId)) {
      return;
    }
    delete map[providerId];
    this._writeFilePayload(map, passphrase);
  }
}

module.exports = {
  BACKEND_TYPES,
  PROVIDER_ENV_MAP,
  SecretsBridge,
  maskSecretFingerprint
};
