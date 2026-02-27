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

function requestJson({ host, port, method, path, headers, body }) {
  return new Promise((resolve, reject) => {
    const req = http.request(
      {
        host,
        port,
        method,
        path,
        headers: headers || {},
      },
      (res) => {
        const chunks = [];
        res.on('data', (c) => chunks.push(c));
        res.on('end', () => {
          resolve({
            statusCode: res.statusCode,
            headers: res.headers || {},
            body: Buffer.concat(chunks).toString('utf8'),
          });
        });
      }
    );
    req.on('error', reject);
    if (body) req.write(body);
    req.end();
  });
}

test('GET /api/procs forwards to /rpc/procs and never returns HTML', async () => {
  let lastUpstreamPath = null;
  const upstream = http.createServer((req, res) => {
    lastUpstreamPath = req.url;
    if (req.url === '/rpc/procs') {
      res.statusCode = 200;
      res.setHeader('content-type', 'application/json; charset=utf-8');
      res.end(JSON.stringify({ ok: true, procs: [] }) + '\n');
      return;
    }
    res.statusCode = 404;
    res.setHeader('content-type', 'application/json; charset=utf-8');
    res.end(JSON.stringify({ ok: false, error: 'upstream_not_found' }) + '\n');
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
    const response = await requestJson({
      host: edgeAddr.host,
      port: edgeAddr.port,
      method: 'GET',
      path: '/api/procs',
      headers: {
        Authorization: 'Bearer edge_token_a',
        Accept: 'text/html',
      },
    });

    assert.equal(response.statusCode, 200);
    assert.match(String(response.headers['content-type'] || ''), /application\/json/i);
    assert.ok(!/<!doctype html>|<html|<openclaw-app/i.test(response.body));
    assert.equal(lastUpstreamPath, '/rpc/procs');
  } finally {
    await edge.close();
    await new Promise((resolve) => upstream.close(resolve));
  }
});
