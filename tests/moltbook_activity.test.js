'use strict';

const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const {
  buildMonthlyImpact,
  parseJsonl
} = require('../scripts/moltbook_activity');

function testMonthlyAggregation() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'moltbook-'));
  const input = path.join(root, 'stub.jsonl');
  fs.writeFileSync(
    input,
    [
      JSON.stringify({ ts_utc: '2026-02-01T12:00:00Z', posts: 1, likes: 3, comments: 2, shares: 1 }),
      JSON.stringify({ ts_utc: '2026-02-10T08:00:00Z', posts: 2, likes: 1, comments: 0, shares: 0 }),
      JSON.stringify({ ts_utc: '2026-03-01T00:00:00Z', posts: 99, likes: 99, comments: 99, shares: 99 })
    ].join('\n') + '\n',
    'utf8'
  );

  const entries = parseJsonl(input);
  const report = buildMonthlyImpact(entries, '2026-02');
  assert.strictEqual(report.posts, 3);
  assert.strictEqual(report.likes, 4);
  assert.strictEqual(report.comments, 2);
  assert.strictEqual(report.shares, 1);
  assert.strictEqual(report.engagements_total, 7);
  console.log('PASS moltbook activity aggregates monthly impact from local stub events');
}

testMonthlyAggregation();
