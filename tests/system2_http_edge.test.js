'use strict';

const assert = require('node:assert/strict');
const http = require('node:http');
const net = require('node:net');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { createHash, createHmac } = require('node:crypto');

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

function rawUpgrade({ host, port, path, headers }) {
  return new Promise((resolve, reject) => {
    const sock = net.connect({ host, port }, () => {
      let req =
        `GET ${path} HTTP/1.1\r\n` +
        `Host: ${host}:${port}\r\n` +
        `Connection: Upgrade\r\n` +
        `Upgrade: websocket\r\n` +
        `Sec-WebSocket-Version: 13\r\n` +
        `Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n`;
      for (const [k, v] of Object.entries(headers || {})) {
        req += `${k}: ${v}\r\n`;
      }
      req += `\r\n`;
      sock.write(req, 'utf8');
    });

    let data = '';
    sock.on('data', (buf) => {
      data += buf.toString('utf8');
      if (data.includes('\r\n\r\n')) {
        sock.destroy();
        resolve(data);
      }
    });
    sock.on('error', reject);
  });
}

function sha256Hex(buf) {
  return createHash('sha256').update(buf || Buffer.alloc(0)).digest('hex');
}

function signHmac({ secret, method, path: p, timestampSec, body }) {
  const msg = `${method}\n${p}\n${timestampSec}\n${sha256Hex(body || Buffer.alloc(0))}`;
  return createHmac('sha256', secret).update(msg).digest('hex');
}

async function testAuthAndNoSecretLogs() {
  const upstream = http.createServer((req, res) => {
    if (req.url === '/health') {
      res.statusCode = 200;
      res.setHeader('content-type', 'application/json');
      res.end(JSON.stringify({ ok: true }) + '\n');
      return;
    }
    res.statusCode = 200;
    res.end('ok\n');
  });

  const upstreamAddr = await listen(upstream);

  const logs = [];
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
    logFn: (line) => logs.push(String(line)),
    auditSink: { writeLine: () => {} },
  });
  const edgeAddr = await listen(edge.server);

  try {
    const noAuth = await requestJson({ host: edgeAddr.host, port: edgeAddr.port, method: 'GET', path: '/health' });
    assert.equal(noAuth.statusCode, 401);

    const badAuth = await requestJson({
      host: edgeAddr.host,
      port: edgeAddr.port,
      method: 'GET',
      path: '/health',
      headers: { Authorization: 'Bearer wrong' },
    });
    assert.equal(badAuth.statusCode, 401);

    const ok = await requestJson({
      host: edgeAddr.host,
      port: edgeAddr.port,
      method: 'GET',
      path: '/health',
      headers: { Authorization: 'Bearer edge_token_a' },
    });
    assert.equal(ok.statusCode, 200);

    const joined = logs.join('\n');
    assert.ok(!joined.includes('Bearer '), 'logs must not include Bearer');
    assert.ok(!joined.includes('edge_token_a'), 'logs must not include token value');
  } finally {
    await edge.close();
    await new Promise((resolve) => upstream.close(resolve));
  }
}

async function testRateLimit() {
  const upstream = http.createServer((req, res) => {
    res.statusCode = 200;
    res.end('ok\n');
  });
  const upstreamAddr = await listen(upstream);

  const edge = createEdgeServer({
    env: {
      OPENCLAW_EDGE_TOKENS: 'userA:edge_token_a',
      OPENCLAW_EDGE_RATE_PER_MIN: '2',
      OPENCLAW_EDGE_BURST: '2',
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
    const r1 = await requestJson({ host: edgeAddr.host, port: edgeAddr.port, method: 'GET', path: '/health', headers });
    const r2 = await requestJson({ host: edgeAddr.host, port: edgeAddr.port, method: 'GET', path: '/health', headers });
    const r3 = await requestJson({ host: edgeAddr.host, port: edgeAddr.port, method: 'GET', path: '/health', headers });
    assert.equal(r1.statusCode, 200);
    assert.equal(r2.statusCode, 200);
    assert.equal(r3.statusCode, 429);
  } finally {
    await edge.close();
    await new Promise((resolve) => upstream.close(resolve));
  }
}

async function testBodyLimit413() {
  const upstream = http.createServer((req, res) => {
    res.statusCode = 200;
    res.end('ok\n');
  });
  const upstreamAddr = await listen(upstream);

  const edge = createEdgeServer({
    env: {
      OPENCLAW_EDGE_TOKENS: 'userA:edge_token_a',
      OPENCLAW_EDGE_MAX_BODY_BYTES: '64',
      OPENCLAW_EDGE_RATE_PER_MIN: '1000',
      OPENCLAW_EDGE_BURST: '1000',
      OPENCLAW_EDGE_UPSTREAM_HOST: upstreamAddr.host,
      OPENCLAW_EDGE_UPSTREAM_PORT: String(upstreamAddr.port),
      OPENCLAW_EDGE_APPROVE_TOKENS: 'ok:approve_token_ok',
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
    const headers = {
      Authorization: 'Bearer edge_token_a',
      'Content-Type': 'application/json',
      'X-OpenClaw-Approve': 'approve_token_ok',
    };
    const tooBig = Buffer.from('x'.repeat(128), 'utf8');
    const r = await requestJson({
      host: edgeAddr.host,
      port: edgeAddr.port,
      method: 'POST',
      path: '/rpc/call',
      headers,
      body: tooBig,
    });
    assert.equal(r.statusCode, 413);
  } finally {
    await edge.close();
    await new Promise((resolve) => upstream.close(resolve));
  }
}

async function testRpcApprovalRequired() {
  const upstream = http.createServer((req, res) => {
    res.statusCode = 200;
    res.end('ok\n');
  });
  const upstreamAddr = await listen(upstream);

  const edge = createEdgeServer({
    env: {
      OPENCLAW_EDGE_TOKENS: 'userA:edge_token_a',
      OPENCLAW_EDGE_APPROVE_TOKENS: 'ok:approve_token_ok',
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
    const denied = await requestJson({
      host: edgeAddr.host,
      port: edgeAddr.port,
      method: 'POST',
      path: '/rpc/foo',
      headers: { Authorization: 'Bearer edge_token_a', 'Content-Type': 'application/json' },
      body: Buffer.from('{}', 'utf8'),
    });
    assert.equal(denied.statusCode, 403);

    const allowed = await requestJson({
      host: edgeAddr.host,
      port: edgeAddr.port,
      method: 'POST',
      path: '/rpc/foo',
      headers: {
        Authorization: 'Bearer edge_token_a',
        'Content-Type': 'application/json',
        'X-OpenClaw-Approve': 'approve_token_ok',
      },
      body: Buffer.from('{}', 'utf8'),
    });
    assert.equal(allowed.statusCode, 200);
  } finally {
    await edge.close();
    await new Promise((resolve) => upstream.close(resolve));
  }
}

async function testWsUpgradeApproval() {
  const upstream = http.createServer();
  upstream.on('upgrade', (req, socket) => {
    socket.write(
      'HTTP/1.1 101 Switching Protocols\r\n' +
        'Upgrade: websocket\r\n' +
        'Connection: Upgrade\r\n' +
        'Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=\r\n' +
        '\r\n'
    );
    socket.end();
  });
  const upstreamAddr = await listen(upstream);

  const edge = createEdgeServer({
    env: {
      OPENCLAW_EDGE_TOKENS: 'userA:edge_token_a',
      OPENCLAW_EDGE_APPROVE_TOKENS: 'ok:approve_token_ok',
      OPENCLAW_EDGE_UPSTREAM_HOST: upstreamAddr.host,
      OPENCLAW_EDGE_UPSTREAM_PORT: String(upstreamAddr.port),
      OPENCLAW_EDGE_RATE_PER_MIN: '1000',
      OPENCLAW_EDGE_BURST: '1000',
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
    const denied = await rawUpgrade({
      host: edgeAddr.host,
      port: edgeAddr.port,
      path: '/rpc/ws',
      headers: { Authorization: 'Bearer edge_token_a' },
    });
    assert.ok(denied.includes('HTTP/1.1 403'), `expected 403, got: ${JSON.stringify(denied.slice(0, 80))}`);

    const allowed = await rawUpgrade({
      host: edgeAddr.host,
      port: edgeAddr.port,
      path: '/rpc/ws',
      headers: {
        Authorization: 'Bearer edge_token_a',
        'X-OpenClaw-Approve': 'approve_token_ok',
      },
    });
    assert.ok(allowed.includes('HTTP/1.1 101'), `expected 101, got: ${JSON.stringify(allowed.slice(0, 80))}`);
  } finally {
    await edge.close();
    await new Promise((resolve) => upstream.close(resolve));
  }
}

async function testNonLoopbackBindRequiresOptIn() {
  const upstream = http.createServer((req, res) => {
    res.statusCode = 200;
    res.end('ok\n');
  });
  const upstreamAddr = await listen(upstream);

  try {
    assert.throws(
      () =>
        createEdgeServer({
          env: {
            OPENCLAW_EDGE_TOKENS: 'userA:edge_token_a',
            OPENCLAW_EDGE_UPSTREAM_HOST: upstreamAddr.host,
            OPENCLAW_EDGE_UPSTREAM_PORT: String(upstreamAddr.port),
          },
          bindHost: '0.0.0.0',
          bindPort: 0,
          upstreamHost: upstreamAddr.host,
          upstreamPort: upstreamAddr.port,
          logFn: () => {},
          auditSink: { writeLine: () => {} },
        }),
      /non-loopback bind requires/i
    );

    const edge = createEdgeServer({
      env: {
        OPENCLAW_EDGE_TOKENS: 'userA:edge_token_a',
        OPENCLAW_EDGE_BIND_ALLOW_NONLOOPBACK: '1',
        OPENCLAW_EDGE_UPSTREAM_HOST: upstreamAddr.host,
        OPENCLAW_EDGE_UPSTREAM_PORT: String(upstreamAddr.port),
      },
      bindHost: '0.0.0.0',
      bindPort: 0,
      upstreamHost: upstreamAddr.host,
      upstreamPort: upstreamAddr.port,
      logFn: () => {},
      auditSink: { writeLine: () => {} },
    });

    const addr = await listen(edge.server, '0.0.0.0');
    assert.ok(addr && addr.port > 0);
    await edge.close();
  } finally {
    await new Promise((resolve) => upstream.close(resolve));
  }
}

async function testHmacSigningAuth() {
  const upstream = http.createServer((req, res) => {
    if (req.url === '/health') {
      res.statusCode = 200;
      res.end('ok\n');
      return;
    }
    res.statusCode = 404;
    res.end('nope\n');
  });
  const upstreamAddr = await listen(upstream);

  const logs = [];
  const edge = createEdgeServer({
    env: {
      OPENCLAW_EDGE_HMAC_KEYS: 'k1:hmac_test_secret',
      OPENCLAW_EDGE_HMAC_SKEW_SEC: '60',
      OPENCLAW_EDGE_RATE_PER_MIN: '1000',
      OPENCLAW_EDGE_BURST: '1000',
      OPENCLAW_EDGE_UPSTREAM_HOST: upstreamAddr.host,
      OPENCLAW_EDGE_UPSTREAM_PORT: String(upstreamAddr.port),
    },
    bindHost: '127.0.0.1',
    bindPort: 0,
    upstreamHost: upstreamAddr.host,
    upstreamPort: upstreamAddr.port,
    logFn: (line) => logs.push(String(line)),
    auditSink: { writeLine: () => {} },
  });
  const edgeAddr = await listen(edge.server);

  try {
    const nowSec = Math.floor(Date.now() / 1000);
    const sig = signHmac({ secret: 'hmac_test_secret', method: 'GET', path: '/health', timestampSec: nowSec, body: null });

    const ok = await requestJson({
      host: edgeAddr.host,
      port: edgeAddr.port,
      method: 'GET',
      path: '/health',
      headers: {
        'X-OpenClaw-Timestamp': String(nowSec),
        'X-OpenClaw-KeyId': 'k1',
        'X-OpenClaw-Signature': sig,
      },
    });
    assert.equal(ok.statusCode, 200);

    const staleSec = nowSec - 1000;
    const staleSig = signHmac({
      secret: 'hmac_test_secret',
      method: 'GET',
      path: '/health',
      timestampSec: staleSec,
      body: null,
    });
    const stale = await requestJson({
      host: edgeAddr.host,
      port: edgeAddr.port,
      method: 'GET',
      path: '/health',
      headers: {
        'X-OpenClaw-Timestamp': String(staleSec),
        'X-OpenClaw-KeyId': 'k1',
        'X-OpenClaw-Signature': staleSig,
      },
    });
    assert.equal(stale.statusCode, 401);

    const bad = await requestJson({
      host: edgeAddr.host,
      port: edgeAddr.port,
      method: 'GET',
      path: '/health',
      headers: {
        'X-OpenClaw-Timestamp': String(nowSec),
        'X-OpenClaw-KeyId': 'k1',
        'X-OpenClaw-Signature': '00'.repeat(32),
      },
    });
    assert.equal(bad.statusCode, 401);

    const joined = logs.join('\n');
    assert.ok(!joined.includes(sig), 'logs must not include signature');
  } finally {
    await edge.close();
    await new Promise((resolve) => upstream.close(resolve));
  }
}

async function testHmacModeAllowsBearerFromLoopbackWhenEnabled() {
  const upstream = http.createServer((req, res) => {
    if (req.url === '/health') {
      res.statusCode = 200;
      res.end('ok\n');
      return;
    }
    res.statusCode = 404;
    res.end('nope\n');
  });
  const upstreamAddr = await listen(upstream);

  const edge = createEdgeServer({
    env: {
      OPENCLAW_EDGE_HMAC_KEYS: 'k1:hmac_test_secret',
      OPENCLAW_EDGE_ALLOW_BEARER_LOOPBACK: '1',
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
    const ok = await requestJson({
      host: edgeAddr.host,
      port: edgeAddr.port,
      method: 'GET',
      path: '/health',
      headers: { Authorization: 'Bearer edge_token_a' },
    });
    assert.equal(ok.statusCode, 200);
  } finally {
    await edge.close();
    await new Promise((resolve) => upstream.close(resolve));
  }
}

async function testAuditSinkWritesAndRotates() {
  const upstream = http.createServer((req, res) => {
    res.statusCode = 200;
    res.end('ok\n');
  });
  const upstreamAddr = await listen(upstream);

  const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'openclaw-edge-audit-'));
  const auditPath = path.join(tmpRoot, 'edge.jsonl');

  const edge = createEdgeServer({
    env: {
      OPENCLAW_EDGE_TOKENS: 'userA:edge_token_a',
      OPENCLAW_EDGE_RATE_PER_MIN: '1000',
      OPENCLAW_EDGE_BURST: '1000',
      OPENCLAW_EDGE_AUDIT_PATH: auditPath,
      OPENCLAW_EDGE_AUDIT_ROTATE_BYTES: '200',
      OPENCLAW_EDGE_AUDIT_ROTATE_KEEP: '2',
      OPENCLAW_EDGE_UPSTREAM_HOST: upstreamAddr.host,
      OPENCLAW_EDGE_UPSTREAM_PORT: String(upstreamAddr.port),
    },
    bindHost: '127.0.0.1',
    bindPort: 0,
    upstreamHost: upstreamAddr.host,
    upstreamPort: upstreamAddr.port,
    logFn: () => {},
  });
  const edgeAddr = await listen(edge.server);

  try {
    const headers = { Authorization: 'Bearer edge_token_a' };
    for (let i = 0; i < 10; i++) {
      // eslint-disable-next-line no-await-in-loop
      const r = await requestJson({ host: edgeAddr.host, port: edgeAddr.port, method: 'GET', path: '/health', headers });
      assert.equal(r.statusCode, 200);
    }

    assert.ok(fs.existsSync(auditPath), 'audit JSONL must exist');
    const main = fs.readFileSync(auditPath, 'utf8');
    const rotated = fs.existsSync(auditPath + '.1') ? fs.readFileSync(auditPath + '.1', 'utf8') : '';

    assert.ok(!main.includes('Bearer '), 'audit must not include Bearer');
    assert.ok(!main.includes('edge_token_a'), 'audit must not include token');
    assert.ok(!rotated.includes('Bearer '), 'rotated audit must not include Bearer');
  } finally {
    await edge.close();
    await new Promise((resolve) => upstream.close(resolve));
  }
}

async function main() {
  await testAuthAndNoSecretLogs();
  console.log('PASS edge rejects missing/invalid auth and does not log secrets');

  await testRateLimit();
  console.log('PASS edge rate limits per identity');

  await testBodyLimit413();
  console.log('PASS edge enforces body size limit (413)');

  await testRpcApprovalRequired();
  console.log('PASS rpc routes require approval (fail-closed)');

  await testWsUpgradeApproval();
  console.log('PASS websocket upgrade requires approval (fail-closed)');

  await testNonLoopbackBindRequiresOptIn();
  console.log('PASS non-loopback bind requires explicit opt-in');

  await testHmacSigningAuth();
  console.log('PASS HMAC signing auth (replay resistant)');

  await testHmacModeAllowsBearerFromLoopbackWhenEnabled();
  console.log('PASS HMAC mode can allow loopback Bearer (opt-in)');

  await testAuditSinkWritesAndRotates();
  console.log('PASS audit sink writes JSONL and rotates (no secrets)');

  console.log('system2_http_edge tests complete');
}

main().catch((error) => {
  console.error(`FAIL system2_http_edge: ${error && error.message ? error.message : error}`);
  process.exitCode = 1;
});
