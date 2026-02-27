'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');

const { createEdgeServer } = require('../scripts/system2_http_edge');

async function listen(server, host = '127.0.0.1') {
  await new Promise((resolve) => server.listen(0, host, resolve));
  const addr = server.address();
  return { host, port: addr.port };
}

function request({ host, port, method, path, headers }) {
  return new Promise((resolve, reject) => {
    const req = http.request({ host, port, method, path, headers: headers || {} }, (res) => {
      const chunks = [];
      res.on('data', (c) => chunks.push(c));
      res.on('end', () => {
        resolve({
          statusCode: res.statusCode,
          headers: res.headers || {},
          body: Buffer.concat(chunks).toString('utf8'),
        });
      });
    });
    req.on('error', reject);
    req.end();
  });
}

test('machine surface never serves html and unknown machine paths are JSON 404', async () => {
  const upstream = http.createServer((req, res) => {
    if (req.url === '/health') {
      res.statusCode = 200;
      res.setHeader('content-type', 'application/json; charset=utf-8');
      res.end(JSON.stringify({ ok: true }) + '\n');
      return;
    }
    res.statusCode = 200;
    res.setHeader('content-type', 'text/plain; charset=utf-8');
    res.end('ok\n');
  });
  const upstreamAddr = await listen(upstream);

  const edge = createEdgeServer({
    env: {
      OPENCLAW_EDGE_TOKENS: 'userA:edge_token_a',
      OPENCLAW_EDGE_RATE_PER_MIN: '1000',
      OPENCLAW_EDGE_BURST: '1000',
      OPENCLAW_EDGE_UPSTREAM_HOST: upstreamAddr.host,
      OPENCLAW_EDGE_UPSTREAM_PORT: String(upstreamAddr.port),
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
    const headers = { Authorization: 'Bearer edge_token_a' };
    const paths = ['/health', '/ready', '/diag/runtime', '/api/does-not-exist', '/diag/does-not-exist'];
    for (const p of paths) {
      // eslint-disable-next-line no-await-in-loop
      const r = await request({ host: edgeAddr.host, port: edgeAddr.port, method: 'GET', path: p, headers });
      assert.ok(r.statusCode === 200 || r.statusCode === 404 || r.statusCode === 503, `${p} status=${r.statusCode}`);
      assert.match(String(r.headers['content-type'] || ''), /application\/json/i, `${p} should be JSON`);
      assert.ok(!/<!doctype html>|<html/i.test(r.body), `${p} must never return HTML`);
    }

    const apiMissing = await request({
      host: edgeAddr.host,
      port: edgeAddr.port,
      method: 'GET',
      path: '/api/unknown',
      headers,
    });
    assert.equal(apiMissing.statusCode, 404);
    assert.match(String(apiMissing.headers['content-type'] || ''), /application\/json/i);

    const diagMissing = await request({
      host: edgeAddr.host,
      port: edgeAddr.port,
      method: 'GET',
      path: '/diag/unknown',
      headers,
    });
    assert.equal(diagMissing.statusCode, 404);
    assert.match(String(diagMissing.headers['content-type'] || ''), /application\/json/i);
  } finally {
    await edge.close();
    await new Promise((resolve) => upstream.close(resolve));
  }
});
