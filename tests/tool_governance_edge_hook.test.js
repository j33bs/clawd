'use strict';

const assert = require('node:assert');
const { _test } = require('../scripts/system2_http_edge');

function testApprovalStatusMapping() {
  assert.strictEqual(_test.approvalStatusFromError({ code: 'APPROVAL_REQUIRED' }), 403);
  assert.strictEqual(_test.approvalStatusFromError({ code: 'TOOL_DENIED' }), 403);
  assert.strictEqual(_test.approvalStatusFromError({ code: 'UNKNOWN' }), 500);
  console.log('PASS http edge governance hook maps approval/deny errors deterministically');
}

testApprovalStatusMapping();
