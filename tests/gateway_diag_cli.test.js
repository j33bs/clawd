'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');
const {
  buildSnapshot,
  toPlain,
  parseArgs,
} = require('../scripts/openclaw_gateway_diag');

function run(name, fn) {
  try {
    fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}: ${error.message}`);
    process.exitCode = 1;
  }
}

run('gateway diag snapshot includes routing and guard env values', () => {
  const payload = buildSnapshot({
    env: {
      ...process.env,
      OPENCLAW_PROVIDER_ALLOWLIST: 'local_vllm,minimax-portal',
      OPENCLAW_DEFAULT_PROVIDER: 'minimax-portal',
      OPENCLAW_ALLOW_CROSSFAMILY_FALLBACK: '0',
      OPENCLAW_STRICT_TOOL_PAYLOAD: '1',
      OPENCLAW_TRACE_VLLM_OUTBOUND: '1',
      OPENCLAW_VLLM_TOKEN_GUARD: '1',
      OPENCLAW_VLLM_TOKEN_GUARD_MODE: 'reject',
      OPENCLAW_VLLM_CONTEXT_MAX_TOKENS: '8192',
    },
    argv: [process.execPath, path.join(process.cwd(), 'scripts', 'openclaw_gateway_diag.js')],
    cwd: process.cwd(),
  });

  assert.equal(payload.routing.default_provider.value, 'minimax-portal');
  assert.deepEqual(payload.routing.provider_allowlist.parsed, ['local_vllm', 'minimax-portal']);
  assert.equal(payload.routing.cross_family_fallback.enabled, false);
  assert.equal(payload.guards.OPENCLAW_STRICT_TOOL_PAYLOAD.value, '1');
  assert.equal(payload.runtime.env_presence.OPENCLAW_VLLM_TOKEN_GUARD.value, '1');
  assert.equal(typeof payload.runtime.key_modules.openai_completions_provider_gate, 'string');
  assert.ok(payload.runtime.key_modules.openai_completions_provider_gate.length > 0);
  assert.equal(typeof payload.versions.node, 'string');
});

run('gateway diag plain rendering includes expected sections', () => {
  const payload = buildSnapshot({
    env: {
      ...process.env,
      OPENCLAW_VLLM_TOKEN_GUARD_MODE: 'truncate',
    },
    argv: [process.execPath, path.join(process.cwd(), 'scripts', 'openclaw_gateway_diag.js')],
    cwd: process.cwd(),
  });
  const out = toPlain(payload);
  assert.match(out, /^ROUTING\n/m);
  assert.match(out, /^GUARDS\n/m);
  assert.match(out, /^RUNTIME\n/m);
  assert.match(out, /^VERSIONS\n/m);
  assert.match(out, /OPENCLAW_VLLM_TOKEN_GUARD_MODE: present=true value=truncate/);
});

run('gateway diag parseArgs enables plain mode flag', () => {
  assert.equal(parseArgs([]).plain, false);
  assert.equal(parseArgs(['--plain']).plain, true);
});

console.log('gateway_diag_cli tests complete');
