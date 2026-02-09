'use strict';

const DEFAULT_CONFIG = {
  featureFlags: {
    systemEvolution: false,
    semanticGraph: false,
    slowLoop: false
  },
  paths: {
    stateDir: 'sys/state',
    templatesDir: 'sys/templates'
  },
  models: {
    default: 'openai/gpt-5-chat-latest'
  }
};

function loadConfig() {
  return JSON.parse(JSON.stringify(DEFAULT_CONFIG));
}

module.exports = {
  DEFAULT_CONFIG,
  loadConfig
};
