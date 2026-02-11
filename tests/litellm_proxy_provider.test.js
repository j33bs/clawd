'use strict';

const assert = require('node:assert');
const http = require('node:http');

const LiteLlmProxyProvider = require('../core/providers/litellm_proxy_provider');
const { normalizeProviderError } = require('../core/normalize_error');

function run(name, fn) {
  return Promise.resolve()
    .then(fn)
    .then(() => {
      console.log(`PASS ${name}`);
    })
    .catch((error) => {
      console.error(`FAIL ${name}`);
      console.error(error.message);
      process.exit(1);
    });
}

function startServer(handler) {
  return new Promise((resolve, reject) => {
    const server = http.createServer(handler);
    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      if (!address || typeof address !== 'object') {
        reject(new Error('server did not return address'));
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
  await run('litellm provider health and call success', async () => {
    const runtime = await startServer((req, res) => {
      if (req.url === '/v1/models') {
        res.writeHead(200, { 'content-type': 'application/json' });
        res.end(JSON.stringify({ data: [] }));
        return;
      }
      if (req.url === '/v1/chat/completions') {
        res.writeHead(200, { 'content-type': 'application/json' });
        res.end(
          JSON.stringify({
            choices: [{ message: { content: 'litellm-ok' } }],
            usage: { prompt_tokens: 12, completion_tokens: 8, total_tokens: 20 }
          })
        );
        return;
      }
      res.writeHead(404, { 'content-type': 'application/json' });
      res.end(JSON.stringify({ error: { message: 'missing' } }));
    });

    try {
      const provider = new LiteLlmProxyProvider({
        baseUrl: runtime.baseUrl
      });
      const health = await provider.health();
      assert.strictEqual(health.ok, true);

      const result = await provider.call({
        messages: [{ role: 'user', content: 'hello' }],
        metadata: {}
      });
      assert.strictEqual(result.text, 'litellm-ok');
      assert.strictEqual(result.usage.totalTokens, 20);
    } finally {
      runtime.server.close();
    }
  });

  await run('litellm provider maps rate limit error', async () => {
    const runtime = await startServer((req, res) => {
      if (req.url === '/v1/chat/completions') {
        res.writeHead(429, { 'content-type': 'application/json' });
        res.end(JSON.stringify({ error: { type: 'rate_limit', message: 'limited' } }));
        return;
      }
      res.writeHead(200, { 'content-type': 'application/json' });
      res.end(JSON.stringify({ data: [] }));
    });

    try {
      const provider = new LiteLlmProxyProvider({
        baseUrl: runtime.baseUrl
      });

      let didThrow = false;
      try {
        await provider.call({
          messages: [{ role: 'user', content: 'hello' }],
          metadata: {}
        });
      } catch (error) {
        didThrow = true;
        const normalized = normalizeProviderError(error, 'LITELLM_PROXY');
        assert.strictEqual(normalized.code, 'RATE_LIMIT');
      }
      assert.strictEqual(didThrow, true);
    } finally {
      runtime.server.close();
    }
  });
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
