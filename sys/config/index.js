'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { DEFAULT_CONFIG } = require('./defaults');
const { parseToml } = require('./toml');

const DEFAULT_CONFIG_PATH = path.join(__dirname, '..', 'config.toml');
const ENV_PREFIX = 'SYS__';

function deepClone(value) {
  return JSON.parse(JSON.stringify(value));
}

function deepMerge(base, extra) {
  if (!extra || typeof extra !== 'object' || Array.isArray(extra)) {
    return base;
  }

  Object.keys(extra).forEach((key) => {
    const incoming = extra[key];
    if (incoming && typeof incoming === 'object' && !Array.isArray(incoming)) {
      if (!base[key] || typeof base[key] !== 'object' || Array.isArray(base[key])) {
        base[key] = {};
      }
      deepMerge(base[key], incoming);
      return;
    }
    base[key] = incoming;
  });

  return base;
}

function convertEnvValue(value) {
  if (value === 'true') {
    return true;
  }
  if (value === 'false') {
    return false;
  }
  if (/^-?\d+(\.\d+)?$/.test(value)) {
    return Number(value);
  }
  return value;
}

function envOverridesToObject(env) {
  const output = {};

  Object.keys(env || {}).forEach((key) => {
    if (!key.startsWith(ENV_PREFIX)) {
      return;
    }

    const rawPath = key.slice(ENV_PREFIX.length);
    if (!rawPath) {
      return;
    }

    const pathParts = rawPath
      .split('__')
      .map((part) => part.trim().toLowerCase())
      .filter(Boolean);

    if (pathParts.length === 0) {
      return;
    }

    let cursor = output;
    for (let i = 0; i < pathParts.length - 1; i += 1) {
      const segment = pathParts[i];
      if (!cursor[segment] || typeof cursor[segment] !== 'object' || Array.isArray(cursor[segment])) {
        cursor[segment] = {};
      }
      cursor = cursor[segment];
    }

    cursor[pathParts[pathParts.length - 1]] = convertEnvValue(env[key]);
  });

  return output;
}

function getType(value) {
  if (Array.isArray(value)) {
    return 'array';
  }
  if (value === null) {
    return 'null';
  }
  return typeof value;
}

function validateAgainstSchema(config, schemaNode, nodePath = '$', errors = []) {
  if (!schemaNode || typeof schemaNode !== 'object') {
    return errors;
  }

  if (schemaNode.type) {
    const actualType = getType(config);
    const expectedType = schemaNode.type;
    if (actualType !== expectedType) {
      errors.push(`${nodePath}: expected ${expectedType}, got ${actualType}`);
      return errors;
    }
  }

  if (schemaNode.required && Array.isArray(schemaNode.required) && config && typeof config === 'object') {
    schemaNode.required.forEach((requiredKey) => {
      if (!Object.prototype.hasOwnProperty.call(config, requiredKey)) {
        errors.push(`${nodePath}: missing required key ${requiredKey}`);
      }
    });
  }

  if (schemaNode.properties && config && typeof config === 'object') {
    Object.keys(schemaNode.properties).forEach((propertyKey) => {
      if (!Object.prototype.hasOwnProperty.call(config, propertyKey)) {
        return;
      }
      validateAgainstSchema(
        config[propertyKey],
        schemaNode.properties[propertyKey],
        `${nodePath}.${propertyKey}`,
        errors
      );
    });
  }

  return errors;
}

function validateConfig(config) {
  const schemaPath = path.join(__dirname, 'config.schema.json');
  const schema = JSON.parse(fs.readFileSync(schemaPath, 'utf8'));
  const errors = validateAgainstSchema(config, schema, '$', []);
  return {
    ok: errors.length === 0,
    errors
  };
}

function loadConfig(options = {}) {
  const configPath = options.configPath || process.env.SYS_CONFIG_PATH || DEFAULT_CONFIG_PATH;
  const env = options.env || process.env;
  const cliOverrides = options.cliOverrides || {};

  const config = deepClone(DEFAULT_CONFIG);

  if (fs.existsSync(configPath)) {
    const parsedToml = parseToml(fs.readFileSync(configPath, 'utf8'));
    deepMerge(config, parsedToml);
  }

  const envOverrides = envOverridesToObject(env);
  deepMerge(config, envOverrides);
  deepMerge(config, cliOverrides);

  const validation = validateConfig(config);
  if (!validation.ok) {
    const error = new Error(`Invalid sys config: ${validation.errors.join('; ')}`);
    error.validationErrors = validation.errors;
    throw error;
  }

  config.__meta = {
    configPath,
    envOverrideKeys: Object.keys(env).filter((key) => key.startsWith(ENV_PREFIX)),
    loadedAt: new Date().toISOString()
  };

  return config;
}

function watchConfig(options = {}) {
  const configPath = options.configPath || process.env.SYS_CONFIG_PATH || DEFAULT_CONFIG_PATH;
  const onReload = typeof options.onReload === 'function' ? options.onReload : () => {};
  const onError = typeof options.onError === 'function' ? options.onError : () => {};

  let timeout = null;
  const watcher = fs.watch(configPath, { persistent: false }, () => {
    if (timeout) {
      clearTimeout(timeout);
    }
    timeout = setTimeout(() => {
      try {
        const config = loadConfig({ configPath });
        onReload({
          type: 'config_hot_reload',
          configPath,
          loadedAt: config.__meta.loadedAt,
          config
        });
      } catch (error) {
        onError(error);
      }
    }, 50);
  });

  return () => {
    if (timeout) {
      clearTimeout(timeout);
    }
    watcher.close();
  };
}

module.exports = {
  DEFAULT_CONFIG_PATH,
  loadConfig,
  watchConfig,
  validateConfig,
  envOverridesToObject,
  deepMerge,
  deepClone
};
