import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';

import { installHttpIngressContractSignal } from '../workspace/runtime_hardening/src/http_ingress_contract_signal.mjs';
import { _resetRateLimitForTest } from '../workspace/runtime_hardening/src/contract_signal.mjs';

test('ingress hook appends service_request for interactive path', async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'openclaw-contract-ingress-'));
  process.env.OPENCLAW_CONTRACT_STATE_DIR = tmp;
  process.env.OPENCLAW_CONTRACT_INGRESS_PORTS = '';
  _resetRateLimitForTest();

  const installed = installHttpIngressContractSignal();
  assert.equal(installed.ok, true);

  const server = http.createServer((req, res) => {
    res.writeHead(200, { 'content-type': 'text/plain' });
    res.end('ok');
  });

  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const { port } = server.address();

  await new Promise((resolve, reject) => {
    const req = http.get({ host: '127.0.0.1', port, path: '/api/test' }, (res) => {
      res.resume();
      res.on('end', resolve);
    });
    req.on('error', reject);
  });

  await new Promise((resolve) => server.close(resolve));

  const signalPath = path.join(tmp, 'signals', 'activity.jsonl');
  assert.equal(fs.existsSync(signalPath), true);
  const lines = fs.readFileSync(signalPath, 'utf8').trim().split('\n');
  assert.ok(lines.length >= 1);

  const event = JSON.parse(lines.at(-1));
  assert.equal(event.kind, 'service_request');
  assert.equal(event.meta.path, '/api/test');

  delete process.env.OPENCLAW_CONTRACT_STATE_DIR;
  delete process.env.OPENCLAW_CONTRACT_INGRESS_PORTS;
});
