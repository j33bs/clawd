'use strict';

const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');

function run(context = {}) {
  const configPath = context.openclawConfigPath || path.join(os.homedir(), '.openclaw', 'openclaw.json');
  if (!fs.existsSync(configPath)) {
    return {
      name: 'default_model_projection_audit',
      status: 'missing_config',
      configPath
    };
  }

  const parsed = JSON.parse(fs.readFileSync(configPath, 'utf8'));
  const defaults = parsed?.agents?.defaults?.model || {};
  return {
    name: 'default_model_projection_audit',
    status: 'ok',
    configPath,
    primary: defaults.primary || null,
    fallbacks: defaults.fallbacks || []
  };
}

module.exports = { run };
