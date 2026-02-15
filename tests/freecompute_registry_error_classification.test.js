#!/usr/bin/env node
'use strict';

const assert = require('node:assert');

const { _test } = require('../core/system2/inference/provider_registry');

function test(name, fn) {
  try {
    fn();
    console.log('PASS ' + name);
  } catch (error) {
    console.error('FAIL ' + name + ': ' + error.message);
    process.exitCode = 1;
  }
}

test('classifyDispatchError: timeout', function () {
  assert.equal(_test.classifyDispatchError({ code: 'PROVIDER_TIMEOUT', message: 'timeout connecting to x' }), 'timeout');
  assert.equal(_test.classifyDispatchError({ message: 'request timeout after 10s' }), 'timeout');
});

test('classifyDispatchError: auth/config/http', function () {
  assert.equal(_test.classifyDispatchError({ code: 'PROVIDER_HTTP_ERROR', statusCode: 401, message: 'http 401' }), 'auth');
  assert.equal(_test.classifyDispatchError({ code: 'PROVIDER_HTTP_ERROR', statusCode: 403, message: 'http 403' }), 'auth');
  assert.equal(_test.classifyDispatchError({ code: 'PROVIDER_HTTP_ERROR', statusCode: 429, message: 'http 429' }), 'rate_limit');
  assert.equal(_test.classifyDispatchError({ code: 'PROVIDER_HTTP_ERROR', statusCode: 404, message: 'http 404' }), 'config');
  assert.equal(_test.classifyDispatchError({ code: 'PROVIDER_HTTP_ERROR', statusCode: 500, message: 'http 500' }), 'http_error');
});
