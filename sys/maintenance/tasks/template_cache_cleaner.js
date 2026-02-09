'use strict';

const { clearTemplateCache } = require('../../render');

function run() {
  clearTemplateCache();
  return {
    name: 'template_cache_cleaner',
    cleared: true
  };
}

module.exports = { run };
