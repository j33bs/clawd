import os from 'node:os';

const PATCH_KEY = '__openclaw_network_enum_guard';

function toErrorMessage(error) {
  if (!error) return 'unknown error';
  if (typeof error.message === 'string' && error.message.trim()) return error.message.trim();
  return String(error);
}

function shouldEmitStatusWarning(processLike) {
  const argv = Array.isArray(processLike?.argv) ? processLike.argv : [];
  return argv.includes('status');
}

export function installNetworkInterfacesGuard({
  osModule = os,
  processLike = process,
  logger = null
} = {}) {
  const existing = globalThis[PATCH_KEY];
  if (existing?.patched) return existing;
  if (!osModule || typeof osModule.networkInterfaces !== 'function') {
    return { patched: false, reason: 'networkInterfaces_unavailable' };
  }

  const original = osModule.networkInterfaces.bind(osModule);
  let warned = false;

  function emitWarning(errorMessage) {
    if (warned) return;
    warned = true;

    if (logger && typeof logger.warn === 'function') {
      logger.warn('network_enum_degraded', {
        code: 'NETWORK_ENUM_DEGRADED',
        error: errorMessage
      });
    }

    if (shouldEmitStatusWarning(processLike)) {
      const line = `NETWORK_ENUM_DEGRADED: ${errorMessage}\n`;
      try {
        processLike?.stderr?.write?.(line);
      } catch {
        // ignore stderr write errors and continue with degraded local checks
      }
    }
  }

  function guardedNetworkInterfaces(...args) {
    try {
      return original(...args);
    } catch (error) {
      emitWarning(toErrorMessage(error));
      return {};
    }
  }

  try {
    osModule.networkInterfaces = guardedNetworkInterfaces;
  } catch (error) {
    const message = toErrorMessage(error);
    if (logger && typeof logger.warn === 'function') {
      logger.warn('network_enum_guard_install_failed', {
        code: 'NETWORK_ENUM_GUARD_INSTALL_FAILED',
        error: message
      });
    }
    return { patched: false, reason: 'assignment_failed', error: message };
  }

  const guard = {
    patched: true,
    restore() {
      try {
        osModule.networkInterfaces = original;
      } finally {
        delete globalThis[PATCH_KEY];
      }
    }
  };

  globalThis[PATCH_KEY] = guard;
  return guard;
}
