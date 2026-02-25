import {
  getConfig,
  redactConfigForLogs,
  logger,
  ensureWorkspaceDirectories,
  SessionManager,
  McpServerSingleflight,
  assertPathWithinRoot,
  sanitizeToolInvocationOrThrow,
  retryWithBackoff
} from './hardening/index.mjs';

const GLOBAL_KEY = '__openclaw_runtime_hardening';

if (!globalThis[GLOBAL_KEY]) {
  const config = getConfig();
  ensureWorkspaceDirectories(config);

  const runtimeLogger = logger.child({ module: 'runtime-hardening-overlay' });
  const sessionManager = new SessionManager({ config, logger: runtimeLogger });

  globalThis[GLOBAL_KEY] = {
    config,
    sessionManager,
    createMcpSingleflight(startServer) {
      return new McpServerSingleflight({
        config,
        logger: runtimeLogger,
        startServer
      });
    },
    assertPathWithinWorkspace(targetPath) {
      return assertPathWithinRoot(config.workspaceRoot, targetPath, {
        allowOutsideWorkspace: config.fsAllowOutsideWorkspace
      });
    },
    sanitizeToolInvocation(payload) {
      return sanitizeToolInvocationOrThrow(payload, { logger: runtimeLogger });
    },
    retryWithBackoff(task, options) {
      return retryWithBackoff(task, {
        logger: runtimeLogger,
        ...options
      });
    }
  };

  runtimeLogger.info('runtime_hardening_initialized', {
    config: redactConfigForLogs(config)
  });
}

export const runtimeHardening = globalThis[GLOBAL_KEY];
