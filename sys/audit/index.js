'use strict';

const schema = require('./schema');
const redaction = require('./redaction');
const logger = require('./logger');
const snapshot = require('./snapshot');
const policy = require('./policy');

module.exports = {
  ...schema,
  ...redaction,
  ...logger,
  ...snapshot,
  ...policy
};
