'use strict';

const fs = require('node:fs');
const path = require('node:path');

const { stableStringify } = require('../canonical_json');

function appendEventJsonl(event) {
  return stableStringify(event) + '\n';
}

async function appendEvent(event, filePath) {
  if (typeof filePath !== 'string' || filePath.length === 0) {
    const err = new Error('filePath required');
    err.code = 'FILEPATH_REQUIRED';
    throw err;
  }
  await fs.promises.mkdir(path.dirname(filePath), { recursive: true });
  await fs.promises.appendFile(filePath, appendEventJsonl(event), 'utf8');
}

module.exports = {
  appendEventJsonl,
  appendEvent
};

