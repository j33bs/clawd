'use strict';

const assert = require('node:assert/strict');

const { UnifiedMemoryQuery } = require('../workspace/memory/unified_query');

function fixtureAdapter(id, rows) {
  return {
    id,
    async query() {
      return rows;
    }
  };
}

async function testMergesAndSortsByTimestampDesc() {
  const query = new UnifiedMemoryQuery({
    adapters: [
      fixtureAdapter('correspondence_store', [
        { ts: '2026-03-01T12:00:00Z', kind: 'section', title: 'older', text: 'body', refs: ['canonical:10'] }
      ]),
      fixtureAdapter('governance_log', [
        { ts: '2026-03-02T12:00:00Z', kind: 'governance_section', title: 'newer', text: 'notes', refs: ['file:oq'] }
      ]),
      fixtureAdapter('vector_store', [
        { ts: null, kind: 'entity', title: 'no-ts', text: 'fallback', refs: ['entity:1'] }
      ])
    ]
  });

  const out = await query.query({ limit: 10 });
  assert.equal(out.length, 3);
  assert.equal(out[0].title, 'newer');
  assert.equal(out[1].title, 'older');
  assert.equal(out[2].title, 'no-ts');
  console.log('PASS unified query merges and sorts by ts desc');
}

async function testSourceFiltering() {
  const query = new UnifiedMemoryQuery({
    adapters: [
      fixtureAdapter('correspondence_store', [{ ts: '2026-03-01T00:00:00Z', title: 'a', text: 'A' }]),
      fixtureAdapter('vector_store', [{ ts: '2026-03-02T00:00:00Z', title: 'b', text: 'B' }])
    ]
  });

  const out = await query.query({ sources: ['vector_store'], limit: 10 });
  assert.equal(out.length, 1);
  assert.equal(out[0].source, 'vector_store');
  console.log('PASS unified query source filtering');
}

async function testLimitEnforcement() {
  const query = new UnifiedMemoryQuery({
    adapters: [
      fixtureAdapter('governance_log', [
        { ts: '2026-03-03T00:00:00Z', title: 'a', text: 'A' },
        { ts: '2026-03-02T00:00:00Z', title: 'b', text: 'B' },
        { ts: '2026-03-01T00:00:00Z', title: 'c', text: 'C' }
      ])
    ]
  });
  const out = await query.query({ limit: 2 });
  assert.equal(out.length, 2);
  assert.deepEqual(out.map((x) => x.title), ['a', 'b']);
  console.log('PASS unified query limit enforcement');
}

async function testQueryAndTagFiltering() {
  const query = new UnifiedMemoryQuery({
    adapters: [
      fixtureAdapter('correspondence_store', [
        { ts: '2026-03-01T00:00:00Z', title: 'Store One', text: 'alpha beta', refs: ['canonical:1', 'exec:gov'] },
        { ts: '2026-03-02T00:00:00Z', title: 'Store Two', text: 'gamma delta', refs: ['canonical:2'] }
      ])
    ]
  });
  const out = await query.query({ q: 'alpha', tags: ['exec:gov'], limit: 10 });
  assert.equal(out.length, 1);
  assert.equal(out[0].title, 'Store One');
  console.log('PASS unified query q/tag filtering');
}

async function testStableOutputShape() {
  const query = new UnifiedMemoryQuery({
    adapters: [
      fixtureAdapter('vector_store', [
        { ts: '2026-03-01T00:00:00Z', kind: 'entity', title: 'Entity', text: 'content', refs: ['entity:abc'], score: 0.42 }
      ])
    ]
  });
  const out = await query.query({ limit: 10 });
  assert.equal(out.length, 1);
  const row = out[0];
  for (const key of ['source', 'ts', 'kind', 'title', 'text', 'refs']) {
    assert.ok(Object.prototype.hasOwnProperty.call(row, key), `missing key ${key}`);
  }
  assert.equal(typeof row.refs.length, 'number');
  assert.equal(typeof row.score, 'number');
  console.log('PASS unified query stable output shape');
}

async function main() {
  await testMergesAndSortsByTimestampDesc();
  await testSourceFiltering();
  await testLimitEnforcement();
  await testQueryAndTagFiltering();
  await testStableOutputShape();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

