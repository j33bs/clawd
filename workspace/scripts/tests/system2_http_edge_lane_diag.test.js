'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');

const { createEdgeServer, _test } = require('../../../scripts/system2_http_edge');

function requestJson({ host, port, method, path, headers, body }) {
  return new Promise((resolve, reject) => {
    const req = http.request({ host, port, method, path, headers: headers || {} }, (res) => {
      const chunks = [];
      res.on('data', (c) => chunks.push(c));
      res.on('end', () => {
        const raw = Buffer.concat(chunks).toString('utf8');
        let parsed = null;
        try {
          parsed = JSON.parse(raw);
        } catch (_) {}
        resolve({ statusCode: res.statusCode, raw, json: parsed });
      });
    });
    req.on('error', reject);
    if (body) req.write(body);
    req.end();
  });
}

async function listen(server, host = '127.0.0.1') {
  await new Promise((resolve) => server.listen(0, host, resolve));
  const addr = server.address();
  return { host, port: addr.port };
}

test('telegram lockout diagnostic handles policy permutations', () => {
  const locked = _test.computeTelegramLaneDiag({
    dmPolicy: 'pairing',
    groupPolicy: 'allowlist',
    allowlist: [],
    pairings: [],
  });
  assert.equal(locked.telegram_lane_locked_out, true);

  const dmPaired = _test.computeTelegramLaneDiag({
    dmPolicy: 'pairing',
    groupPolicy: 'allowlist',
    allowlist: [],
    pairings: ['chat-1'],
  });
  assert.equal(dmPaired.telegram_lane_locked_out, false);

  const groupAllowlisted = _test.computeTelegramLaneDiag({
    dmPolicy: 'allowlist',
    groupPolicy: 'allowlist',
    allowlist: ['12345'],
    pairings: [],
  });
  assert.equal(groupAllowlisted.telegram_lane_locked_out, false);
});

test('ui stale broadcaster diagnostic is deterministic with fake clock', () => {
  const nowMs = 1_800_000_000_000;
  const stale = _test.computeUiLaneDiag({
    activeConnections: 2,
    lastUiEventTs: nowMs - 200_000,
    nowMs,
    staleAfterMs: 120_000,
  });
  assert.equal(stale.ui_broadcaster_stale, true);

  const fresh = _test.computeUiLaneDiag({
    activeConnections: 2,
    lastUiEventTs: nowMs - 1_000,
    nowMs,
    staleAfterMs: 120_000,
  });
  assert.equal(fresh.ui_broadcaster_stale, false);

  const idle = _test.computeUiLaneDiag({
    activeConnections: 0,
    lastUiEventTs: null,
    nowMs,
    staleAfterMs: 120_000,
  });
  assert.equal(idle.ui_broadcaster_stale, false);
});

test('readiness logic degrades on upstream/telegram/ui failures', () => {
  const upstreamBad = _test.computeReadiness({
    upstream: { ok: false, reason: 'html_fallback_not_machine_health' },
    telegram: { telegram_lane_locked_out: false },
    ui: { ui_broadcaster_stale: false },
    maintenanceMode: false,
  });
  assert.equal(upstreamBad.ready, false);
  assert.match(upstreamBad.reasons.join(','), /upstream_unready/);

  const telegramBad = _test.computeReadiness({
    upstream: { ok: true },
    telegram: { telegram_lane_locked_out: true },
    ui: { ui_broadcaster_stale: false },
    maintenanceMode: false,
  });
  assert.equal(telegramBad.ready, false);
  assert.match(telegramBad.reasons.join(','), /telegram_lane_locked_out/);

  const uiBad = _test.computeReadiness({
    upstream: { ok: true },
    telegram: { telegram_lane_locked_out: false },
    ui: { ui_broadcaster_stale: true },
    maintenanceMode: false,
  });
  assert.equal(uiBad.ready, false);
  assert.match(uiBad.reasons.join(','), /ui_broadcaster_stale/);

  const runtimeBad = _test.computeReadiness({
    upstream: { ok: true },
    telegram: { telegram_lane_locked_out: false },
    ui: { ui_broadcaster_stale: false },
    runtime: { event_loop_stalled: true },
    maintenanceMode: false,
  });
  assert.equal(runtimeBad.ready, false);
  assert.match(runtimeBad.reasons.join(','), /event_loop_stalled/);
});

test('runtime diag computes deterministic stall classification', () => {
  const nowMs = 1_800_000_100_000;
  const stalled = _test.computeRuntimeDiag({
    nowMs,
    eventLoopLagMs: 7_500,
    eventLoopLagMaxMs: 7_500,
    eventLoopSamples: 8,
    eventLoopLastSampleTs: nowMs - 7_500,
    eventLoopStallMs: 5_000,
    inflightGlobal: 2,
    inflightIdentities: 1,
  });
  assert.equal(stalled.event_loop_stalled, true);
  assert.equal(stalled.event_loop_stall_after_ms, 5_000);

  const healthy = _test.computeRuntimeDiag({
    nowMs,
    eventLoopLagMs: 5,
    eventLoopLagMaxMs: 40,
    eventLoopSamples: 8,
    eventLoopLastSampleTs: nowMs - 500,
    eventLoopStallMs: 5_000,
    inflightGlobal: 0,
    inflightIdentities: 0,
  });
  assert.equal(healthy.event_loop_stalled, false);
});

test('ready endpoint returns 503 when upstream health is html fallback', async () => {
  const upstream = http.createServer((req, res) => {
    if (req.url === '/health') {
      res.statusCode = 200;
      res.setHeader('content-type', 'text/html; charset=utf-8');
      res.end('<!doctype html><html><body>spa</body></html>');
      return;
    }
    res.statusCode = 404;
    res.end('nope');
  });
  const upstreamAddr = await listen(upstream);

  const edge = createEdgeServer({
    env: {
      OPENCLAW_EDGE_TOKENS: 'userA:edge_token_a',
      OPENCLAW_EDGE_RATE_PER_MIN: '1000',
      OPENCLAW_EDGE_BURST: '1000',
      OPENCLAW_EDGE_UPSTREAM_HOST: upstreamAddr.host,
      OPENCLAW_EDGE_UPSTREAM_PORT: String(upstreamAddr.port),
      OPENCLAW_EDGE_TELEGRAM_DM_POLICY: 'pairing',
      OPENCLAW_EDGE_TELEGRAM_GROUP_POLICY: 'allowlist',
      OPENCLAW_EDGE_TELEGRAM_ALLOWLIST: '',
      OPENCLAW_EDGE_TELEGRAM_PAIRINGS: '',
    },
    bindHost: '127.0.0.1',
    bindPort: 0,
    upstreamHost: upstreamAddr.host,
    upstreamPort: upstreamAddr.port,
    logFn: () => {},
    auditSink: { writeLine: () => {} },
  });
  const edgeAddr = await listen(edge.server);

  try {
    const r = await requestJson({
      host: edgeAddr.host,
      port: edgeAddr.port,
      method: 'GET',
      path: '/ready',
      headers: { Authorization: 'Bearer edge_token_a' },
    });
    assert.equal(r.statusCode, 503);
    assert.equal(Boolean(r.json && r.json.ok), false);
    assert.match(JSON.stringify(r.json || {}), /upstream_unready/);
    assert.match(JSON.stringify(r.json || {}), /telegram_lane_locked_out/);
  } finally {
    await edge.close();
    await new Promise((resolve) => upstream.close(resolve));
  }
});
