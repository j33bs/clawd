'use strict';

const path = require('node:path');
const fs = require('node:fs');

function run(context = {}) {
  const projectRoot = context.projectRoot || process.cwd();
  const inputPath = context.inputPath || '.';
  const resolved = path.resolve(projectRoot, inputPath);
  return {
    name: 'path_autoresolver',
    inputPath,
    resolved,
    exists: fs.existsSync(resolved)
  };
}

module.exports = { run };
