import { getConfig } from './config.mjs';
import { logger as rootLogger } from './log.mjs';

function withTimeout(promise, timeoutMs, key) {
  let timeoutId;
  const timeoutPromise = new Promise((_, reject) => {
    timeoutId = setTimeout(() => {
      reject(new Error(`Timed out starting MCP server "${key}" after ${timeoutMs}ms`));
    }, timeoutMs);
    if (typeof timeoutId.unref === 'function') timeoutId.unref();
  });

  return Promise.race([promise, timeoutPromise]).finally(() => {
    clearTimeout(timeoutId);
  });
}

class McpServerSingleflight {
  constructor(options = {}) {
    if (typeof options.startServer !== 'function') {
      throw new Error('startServer function is required');
    }
    const config = options.config || getConfig();
    this.startServerFn = options.startServer;
    this.timeoutMs = options.timeoutMs || config.mcpServerStartTimeoutMs;
    this.log = (options.logger || rootLogger).child({ module: 'mcp-singleflight' });
    this.inFlight = new Map();
    this.running = new Map();
  }

  isInFlight(key) {
    return this.inFlight.has(key);
  }

  markStopped(key) {
    this.running.delete(key);
  }

  async start(key) {
    const cacheKey = String(key || '').trim();
    if (!cacheKey) throw new Error('server key is required');

    if (this.running.has(cacheKey)) {
      return this.running.get(cacheKey);
    }

    const inFlight = this.inFlight.get(cacheKey);
    if (inFlight) {
      return inFlight;
    }

    const starter = withTimeout(Promise.resolve().then(() => this.startServerFn(cacheKey)), this.timeoutMs, cacheKey)
      .then((handle) => {
        this.running.set(cacheKey, handle);
        return handle;
      })
      .finally(() => {
        this.inFlight.delete(cacheKey);
      })
      .catch((error) => {
        this.log.warn('mcp_server_start_failed', {
          key: cacheKey,
          error
        });
        throw error;
      });

    this.inFlight.set(cacheKey, starter);
    return starter;
  }
}

export { McpServerSingleflight };
