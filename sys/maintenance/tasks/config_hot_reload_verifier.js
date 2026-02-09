'use strict';

const { loadConfig } = require('../../config');

function run(context = {}) {
  const config = loadConfig({
    configPath: context.configPath,
    env: context.env || process.env,
    cliOverrides: context.cliOverrides || {}
  });

  return {
    name: 'config_hot_reload_verifier',
    loadedAt: config.__meta.loadedAt,
    configPath: config.__meta.configPath,
    envOverrideCount: config.__meta.envOverrideKeys.length
  };
}

module.exports = { run };
