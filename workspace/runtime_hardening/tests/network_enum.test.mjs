import test from 'node:test';
import assert from 'node:assert/strict';

import { installNetworkInterfacesGuard } from '../src/network_enum.mjs';

test('network enum guard degrades gracefully for status command', () => {
  const writes = [];
  const warnings = [];

  const fakeOs = {
    networkInterfaces() {
      throw new Error('uv_interface_addresses returned Unknown system error 1');
    }
  };
  const fakeProcess = {
    argv: ['node', 'index.js', 'status', '--verbose'],
    stderr: {
      write(chunk) {
        writes.push(String(chunk));
      }
    }
  };
  const fakeLogger = {
    warn(event, meta) {
      warnings.push({ event, meta });
    }
  };

  const guard = installNetworkInterfacesGuard({
    osModule: fakeOs,
    processLike: fakeProcess,
    logger: fakeLogger
  });

  assert.equal(guard.patched, true);
  assert.doesNotThrow(() => fakeOs.networkInterfaces());
  assert.deepEqual(fakeOs.networkInterfaces(), {});
  assert.equal(warnings.length >= 1, true);
  assert.equal(warnings[0].event, 'network_enum_degraded');
  assert.match(String(writes.join('')), /NETWORK_ENUM_DEGRADED:/);

  guard.restore();
});

test('network enum guard does not emit status warning for non-status commands', () => {
  const writes = [];
  const warnings = [];

  const fakeOs = {
    networkInterfaces() {
      throw new Error('network enumerator unavailable');
    }
  };
  const fakeProcess = {
    argv: ['node', 'index.js', 'agent'],
    stderr: {
      write(chunk) {
        writes.push(String(chunk));
      }
    }
  };
  const fakeLogger = {
    warn(event, meta) {
      warnings.push({ event, meta });
    }
  };

  const guard = installNetworkInterfacesGuard({
    osModule: fakeOs,
    processLike: fakeProcess,
    logger: fakeLogger
  });

  assert.deepEqual(fakeOs.networkInterfaces(), {});
  assert.equal(warnings.length, 1);
  assert.equal(warnings[0].event, 'network_enum_degraded');
  assert.equal(writes.length, 0);

  guard.restore();
});
