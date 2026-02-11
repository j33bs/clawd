'use strict';

const assert = require('node:assert/strict');
const http = require('node:http');
const { System2Gateway } = require('../core/system2/gateway');

function fetch(url, options = {}) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(url);
    const reqOptions = {
      hostname: parsed.hostname,
      port: parsed.port,
      path: parsed.pathname + parsed.search,
      method: options.method || 'GET',
      headers: options.headers || {}
    };

    const req = http.request(reqOptions, (res) => {
      const chunks = [];
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => {
        const body = Buffer.concat(chunks).toString('utf8');
        resolve({
          status: res.statusCode,
          headers: res.headers,
          body,
          json: () => {
            try {
              return JSON.parse(body);
            } catch (_) {
              return null;
            }
          }
        });
      });
    });

    req.on('error', reject);
    if (options.body) {
      req.write(typeof options.body === 'string' ? options.body : JSON.stringify(options.body));
    }
    req.end();
  });
}

async function run(name, fn) {
  try {
    await fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}: ${error.message}`);
    process.exitCode = 1;
  }
}

async function main() {
  // Use a random port to avoid conflicts
  const port = 14100 + Math.floor(Math.random() * 1000);
  const signingKey = 'test-gateway-signing-key-12345';

  // Set env for envelope signing
  process.env.SYSTEM2_ENVELOPE_HMAC_KEY = signingKey;

  const gateway = new System2Gateway({
    port,
    host: '127.0.0.1',
    signingKey,
    callSystem1Fn: async () => ({ ok: true, result: { mock: true } })
  });

  try {
    const startResult = await gateway.start();
    assert.ok(startResult.port);
    assert.ok(startResult.runId);
    assert.ok(startResult.startedAt);

    const base = `http://127.0.0.1:${port}`;

    // --- Health endpoint ---
    await run('GET /health returns status and mode', async () => {
      const res = await fetch(`${base}/health`);
      const data = res.json();
      assert.equal(res.status, 200);
      assert.equal(data.status, 'ok');
      assert.equal(data.gateway, 'system2');
      assert.equal(data.mode, 'normal');
      assert.ok(data.run_id);
    });

    // --- Routing decision ---
    await run('POST /v0/route evaluates routing policy', async () => {
      const res = await fetch(`${base}/v0/route`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          request_type: 'coding',
          privacy_level: 'external_ok',
          urgency: 'interactive',
          provenance: 'first_party',
          tool_needs: ['read_file']
        })
      });
      const data = res.json();
      assert.equal(res.status, 200);
      assert.ok(data.selected_model_route);
      assert.ok(data.degrade_flags);
      assert.ok(data.budget_allocation);
      assert.ok(data.policy_version);
    });

    // --- Tool call ---
    await run('POST /v0/tool executes read-only tool', async () => {
      const res = await fetch(`${base}/v0/tool`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          tool: 'list_dir',
          args: { path: '.' },
          policy: {
            mode: 'allow_readonly',
            allowed_tools: ['list_dir', 'read_file']
          }
        })
      });
      const data = res.json();
      assert.equal(res.status, 200);
      assert.equal(data.ok, true);
    });

    await run('POST /v0/tool denies non-allowlisted tool', async () => {
      const res = await fetch(`${base}/v0/tool`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          tool: 'write_file',
          args: { path: '/tmp/test', content: 'bad' }
        })
      });
      const data = res.json();
      assert.equal(res.status, 403);
      assert.equal(data.ok, false);
    });

    // --- Federated RPC ---
    await run('POST /v0/jobs/submit accepts a job', async () => {
      const res = await fetch(`${base}/v0/jobs/submit`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          target: {
            module: 'core_infra.test',
            fn: 'validate',
            args: [{}]
          }
        })
      });
      const data = res.json();
      assert.equal(res.status, 202);
      assert.equal(data.accepted, true);
      assert.ok(data.jobId);
    });

    await run('POST /v0/jobs/poll returns job status', async () => {
      // Submit first
      const submitRes = await fetch(`${base}/v0/jobs/submit`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          target: { module: 'test', fn: 'run', args: [{}] }
        })
      });
      const submitData = submitRes.json();

      // Wait a tick for async execution
      await new Promise((r) => setTimeout(r, 50));

      const res = await fetch(`${base}/v0/jobs/poll`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ job_id: submitData.jobId })
      });
      const data = res.json();
      assert.equal(res.status, 200);
      assert.equal(data.found, true);
      assert.ok(['accepted', 'running', 'completed'].includes(data.status));
    });

    await run('POST /v0/jobs/cancel cancels a pending job', async () => {
      const submitRes = await fetch(`${base}/v0/jobs/submit`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          target: { module: 'slow', fn: 'task', args: [{}] }
        })
      });
      const submitData = submitRes.json();

      const res = await fetch(`${base}/v0/jobs/cancel`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ job_id: submitData.jobId })
      });
      const data = res.json();
      // May or may not cancel depending on timing
      assert.ok(typeof data.cancelled === 'boolean');
    });

    // --- Mode control ---
    await run('GET /v0/mode returns current mode', async () => {
      const res = await fetch(`${base}/v0/mode`);
      const data = res.json();
      assert.equal(res.status, 200);
      assert.equal(data.mode, 'normal');
    });

    await run('POST /v0/mode transitions mode', async () => {
      const res = await fetch(`${base}/v0/mode`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ mode: 'degraded', reason: 'test' })
      });
      const data = res.json();
      assert.equal(res.status, 200);
      assert.equal(data.mode, 'degraded');

      // Restore normal
      await fetch(`${base}/v0/mode`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ mode: 'normal', reason: 'restore' })
      });
    });

    await run('POST /v0/mode rejects invalid mode', async () => {
      const res = await fetch(`${base}/v0/mode`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ mode: 'invalid' })
      });
      assert.equal(res.status, 400);
    });

    // --- Budget ---
    await run('GET /v0/budget returns budget allocation', async () => {
      const res = await fetch(`${base}/v0/budget`);
      const data = res.json();
      assert.equal(res.status, 200);
      assert.ok(typeof data.remaining === 'number');
      assert.ok(typeof data.cap === 'number');
      assert.equal(data.state, 'closed');
    });

    await run('POST /v0/budget/reset resets budget', async () => {
      const res = await fetch(`${base}/v0/budget/reset`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ tokenCap: 50000 })
      });
      const data = res.json();
      assert.equal(res.status, 200);
      assert.equal(data.cap, 50000);
      assert.equal(data.state, 'closed');
    });

    // --- System-1 health update ---
    await run('POST /v0/system1/health updates system1 state', async () => {
      const res = await fetch(`${base}/v0/system1/health`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ state: 'saturated' })
      });
      const data = res.json();
      assert.equal(res.status, 200);
      assert.equal(data.system1_health.state, 'saturated');
      assert.equal(data.mode.mode, 'burst');

      // Restore
      await fetch(`${base}/v0/system1/health`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ state: 'up' })
      });
    });

    // --- Events ---
    await run('GET /v0/events returns event log', async () => {
      const res = await fetch(`${base}/v0/events?cursor=0`);
      const data = res.json();
      assert.equal(res.status, 200);
      assert.ok(Array.isArray(data.events));
      assert.ok(data.events.length > 0); // gateway_started + routing events
      assert.ok(data.nextCursor);
    });

    // --- 404 ---
    await run('GET unknown path returns 404', async () => {
      const res = await fetch(`${base}/v0/unknown`);
      assert.equal(res.status, 404);
    });

    // --- Degraded mode disables tools ---
    await run('tool call returns 503 when in degraded mode', async () => {
      await fetch(`${base}/v0/mode`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ mode: 'degraded', reason: 'test' })
      });

      const res = await fetch(`${base}/v0/tool`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          tool: 'list_dir',
          args: { path: '.' },
          policy: { mode: 'allow_readonly', allowed_tools: ['list_dir'] }
        })
      });
      assert.equal(res.status, 503);
      const data = res.json();
      assert.equal(data.error, 'tools_disabled');

      // Restore normal
      await fetch(`${base}/v0/mode`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ mode: 'normal', reason: 'restore' })
      });
    });

  } finally {
    await gateway.stop();
    delete process.env.SYSTEM2_ENVELOPE_HMAC_KEY;
  }

  console.log('gateway tests complete');
}

main().catch((error) => {
  console.error(`FATAL: ${error.message}`);
  process.exitCode = 1;
});
