'use strict';

const assert = require('node:assert');
const http = require('node:http');

const { callModel } = require('../core/model_call');
const { createModelRuntime } = require('../core/model_runtime');
const { BACKENDS, TASK_CLASSES } = require('../core/model_constants');

function startServer(handler) {
  return new Promise((resolve, reject) => {
    const server = http.createServer(handler);
    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      if (!address || typeof address !== 'object') {
        reject(new Error('failed to get server address'));
        return;
      }
      resolve({
        server,
        baseUrl: `http://127.0.0.1:${address.port}/v1`
      });
    });
  });
}

async function main() {
  process.env.OPENCLAW_SYSTEM2_POLICY_ENFORCE = '1';

  const runtimeServer = await startServer((req, res) => {
    if (req.url === '/v1/models') {
      res.writeHead(200, { 'content-type': 'application/json' });
      res.end(JSON.stringify({ data: [] }));
      return;
    }
    if (req.url === '/v1/chat/completions') {
      res.writeHead(200, { 'content-type': 'application/json' });
      res.end(
        JSON.stringify({
          choices: [{ message: { content: 'litellm-routed' } }],
          usage: { prompt_tokens: 10, completion_tokens: 10, total_tokens: 20 }
        })
      );
      return;
    }
    res.writeHead(404, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ error: { message: 'not-found' } }));
  });

  try {
    global.__OPENCLAW_MODEL_RUNTIME = createModelRuntime({
      persistLogs: false,
      useLiteLlmProxy: true,
      litellm: {
        baseUrl: runtimeServer.baseUrl
      }
    });

    const result = await callModel({
      taskId: 'system2_litellm_route',
      messages: [{ role: 'user', content: 'analyze this' }],
      taskClass: TASK_CLASSES.NON_BASIC,
      metadata: {
        system2_policy_input: {
          request_type: 'coding',
          privacy_level: 'external_ok',
          budget: {
            remaining: 5000,
            cap: 10000
          }
        }
      }
    });

    assert.strictEqual(result.backend, BACKENDS.LITELLM_PROXY);
    assert.strictEqual(result.response.text, 'litellm-routed');
    console.log('PASS model call routes to litellm when system2 policy selects coding route');
  } finally {
    runtimeServer.server.close();
  }
}

main().catch((error) => {
  console.error(`FAIL model call routes to litellm when system2 policy selects coding route`);
  console.error(error.message);
  process.exit(1);
});
