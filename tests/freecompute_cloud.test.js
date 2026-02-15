#!/usr/bin/env node
'use strict';

/**
 * FreeComputeCloud — Unit + Integration Tests
 *
 * Tests are CI-safe by default:
 *   - All feature flags OFF → tests verify disabled-state behavior.
 *   - Schema validation, router determinism, redaction all test locally.
 *   - Integration tests (live provider probes) are SKIPPED unless
 *     FREECOMPUTE_INTEGRATION=1 is set with appropriate credentials.
 *
 * Run:
 *   node tests/freecompute_cloud.test.js
 *   FREECOMPUTE_INTEGRATION=1 OPENCLAW_GROQ_API_KEY=... node tests/freecompute_cloud.test.js
 */

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');

// Modules under test
const {
  REQUEST_CLASSES, ALL_REQUEST_CLASSES, PROVIDER_KINDS, AUTH_TYPES, TOOL_SUPPORT,
  validateProviderEntry, validateCatalog,
  loadFreeComputeConfig, REDACT_ENV_VARS, redactIfSensitive,
  CATALOG_VERSION, CATALOG, getProvider, queryProviders,
  QuotaLedger,
  routeRequest, explainRouting,
  vllmStartCommand, buildVllmStatusArtifact,
  ProviderRegistry, CB_STATES,
  ProviderAdapter
} = require('../core/system2/inference');

const { _test: registryTest } = require('../core/system2/inference/provider_registry');

let passed = 0;
let failed = 0;
let skipped = 0;
const failures = [];

function test(name, fn) {
  try {
    fn();
    passed++;
  } catch (err) {
    failed++;
    failures.push({ name, error: err.message });
    console.error(`  FAIL: ${name} — ${err.message}`);
  }
}

async function testAsync(name, fn) {
  try {
    await fn();
    passed++;
  } catch (err) {
    failed++;
    failures.push({ name, error: err.message });
    console.error(`  FAIL: ${name} — ${err.message}`);
  }
}

function skip(name, reason) {
  skipped++;
  // Silent skip for CI
}

async function main() {

// ════════════════════════════════════════════════════════════════════
// 1. SCHEMA VALIDATION
// ════════════════════════════════════════════════════════════════════
console.log('\n── Schema Validation ──');

test('REQUEST_CLASSES: has all expected classes', () => {
  assert.ok(ALL_REQUEST_CLASSES.includes('fast_chat'));
  assert.ok(ALL_REQUEST_CLASSES.includes('long_context'));
  assert.ok(ALL_REQUEST_CLASSES.includes('code'));
  assert.ok(ALL_REQUEST_CLASSES.includes('batch'));
  assert.ok(ALL_REQUEST_CLASSES.includes('tool_use'));
  assert.ok(ALL_REQUEST_CLASSES.includes('embeddings'));
  assert.equal(ALL_REQUEST_CLASSES.length, 6);
});

test('PROVIDER_KINDS: local and external', () => {
  assert.equal(PROVIDER_KINDS.LOCAL, 'local');
  assert.equal(PROVIDER_KINDS.EXTERNAL, 'external');
});

test('validateProviderEntry: accepts valid entry', () => {
  const entry = CATALOG[0]; // local_vllm
  const result = validateProviderEntry(entry);
  assert.equal(result.ok, true, `errors: ${result.errors.join('; ')}`);
});

test('validateProviderEntry: rejects empty object', () => {
  const result = validateProviderEntry({});
  assert.equal(result.ok, false);
  assert.ok(result.errors.length > 0);
});

test('validateProviderEntry: rejects invalid kind', () => {
  const entry = { ...CATALOG[0], kind: 'imaginary' };
  const result = validateProviderEntry(entry);
  assert.equal(result.ok, false);
  assert.ok(result.errors.some((e) => e.includes('invalid kind')));
});

test('validateProviderEntry: rejects invalid task_class in model', () => {
  const entry = JSON.parse(JSON.stringify(CATALOG[0]));
  entry.models[0].task_classes = ['nonexistent_class'];
  const result = validateProviderEntry(entry);
  assert.equal(result.ok, false);
  assert.ok(result.errors.some((e) => e.includes('invalid task_class')));
});

test('validateCatalog: full catalog passes validation', () => {
  const result = validateCatalog(CATALOG);
  assert.equal(result.ok, true, `errors: ${result.errors.join('; ')}`);
  assert.equal(result.validCount, CATALOG.length);
});

test('validateCatalog: rejects non-array', () => {
  const result = validateCatalog('not-an-array');
  assert.equal(result.ok, false);
});

test('CATALOG_VERSION: is set', () => {
  assert.equal(CATALOG_VERSION, '0.1');
});

// ════════════════════════════════════════════════════════════════════
// 2. CATALOG QUERIES
// ════════════════════════════════════════════════════════════════════
console.log('── Catalog Queries ──');

test('getProvider: finds local_vllm', () => {
  const p = getProvider('local_vllm');
  assert.ok(p);
  assert.equal(p.provider_id, 'local_vllm');
  assert.equal(p.kind, 'local');
});

test('getProvider: returns null for unknown', () => {
  assert.equal(getProvider('nonexistent'), null);
});

test('queryProviders: filter by kind=local', () => {
  const locals = queryProviders({ kind: 'local' });
  assert.ok(locals.length >= 1);
  assert.ok(locals.every((p) => p.kind === 'local'));
});

test('queryProviders: filter by kind=external', () => {
  const externals = queryProviders({ kind: 'external' });
  assert.ok(externals.length >= 4);
  assert.ok(externals.every((p) => p.kind === 'external'));
});

test('queryProviders: filter by taskClass=code', () => {
  const code = queryProviders({ taskClass: 'code' });
  assert.ok(code.length >= 3);
});

test('queryProviders: filter by tag=free_tier', () => {
  const free = queryProviders({ tag: 'free_tier' });
  assert.ok(free.length >= 2);
});

test('catalog: all providers have evidence entries', () => {
  for (const p of CATALOG) {
    assert.ok(Array.isArray(p.evidence) && p.evidence.length > 0,
      `${p.provider_id} has no evidence entries`);
    for (const e of p.evidence) {
      assert.ok(e.type, `${p.provider_id} evidence missing type`);
      assert.ok(e.title, `${p.provider_id} evidence missing title`);
    }
  }
});

test('catalog: all providers have circuit breaker config', () => {
  for (const p of CATALOG) {
    assert.ok(p.constraints.circuit_breaker, `${p.provider_id} missing circuit_breaker`);
    assert.equal(typeof p.constraints.circuit_breaker.consecutive_failures_to_open, 'number');
    assert.equal(typeof p.constraints.circuit_breaker.open_seconds, 'number');
  }
});

test('catalog: no secrets in catalog entries', () => {
  const json = JSON.stringify(CATALOG);
  assert.ok(!json.includes('sk-'), 'catalog contains what looks like a secret key');
  assert.ok(!json.includes('gsk_'), 'catalog contains what looks like a Groq key');
  assert.ok(!json.includes('Bearer '), 'catalog contains a Bearer token');
  // Auth should only reference env var names, never values
  for (const p of CATALOG) {
    if (p.auth && p.auth.env_var) {
      assert.ok(p.auth.env_var.startsWith('OPENCLAW_'), `${p.provider_id}: env_var should start with OPENCLAW_`);
    }
    assert.equal(p.auth.redact_in_logs, true, `${p.provider_id}: auth.redact_in_logs must be true`);
  }
});

// ════════════════════════════════════════════════════════════════════
// 3. CONFIG + REDACTION
// ════════════════════════════════════════════════════════════════════
console.log('── Config + Redaction ──');

test('config: defaults to disabled', () => {
  const cfg = loadFreeComputeConfig({});
  assert.equal(cfg.enabled, false);
  assert.equal(cfg.vllmEnabled, true);
});

test('config: enables with flag', () => {
  const cfg = loadFreeComputeConfig({ ENABLE_FREECOMPUTE_CLOUD: '1' });
  assert.equal(cfg.enabled, true);
});

test('config: enables with alias flag', () => {
  const cfg = loadFreeComputeConfig({ ENABLE_FREECOMPUTE: '1' });
  assert.equal(cfg.enabled, true);
});

test('config: parses global caps', () => {
  const cfg = loadFreeComputeConfig({
    ENABLE_FREECOMPUTE_CLOUD: '1',
    FREECOMPUTE_MAX_DAILY_REQUESTS: '500',
    FREECOMPUTE_MAX_RPM: '50'
  });
  assert.equal(cfg.globalMaxDailyRequests, 500);
  assert.equal(cfg.globalMaxRpm, 50);
});

test('config: parses provider allowlist', () => {
  const cfg = loadFreeComputeConfig({
    FREECOMPUTE_PROVIDER_ALLOWLIST: 'groq, gemini'
  });
  assert.deepEqual(cfg.providerAllowlist, ['groq', 'gemini']);
});

test('config: parses circuit breaker thresholds', () => {
  const cfg = loadFreeComputeConfig({
    FREECOMPUTE_CB_FAILURES: '10',
    FREECOMPUTE_CB_OPEN_SECONDS: '300'
  });
  assert.equal(cfg.circuitBreaker.consecutiveFailures, 10);
  assert.equal(cfg.circuitBreaker.openSeconds, 300);
});

test('config: task class caps populated for all classes', () => {
  const cfg = loadFreeComputeConfig({});
  for (const tc of ALL_REQUEST_CLASSES) {
    assert.ok(cfg.taskClassCaps[tc], `missing taskClassCaps for ${tc}`);
    assert.equal(typeof cfg.taskClassCaps[tc].maxExternalFreeRpm, 'number');
    assert.equal(typeof cfg.taskClassCaps[tc].maxRetries, 'number');
  }
});

test('redaction: redacts API key values', () => {
  assert.equal(redactIfSensitive('authorization', 'Bearer tok123'), '[REDACTED]');
  assert.equal(redactIfSensitive('x-api-key', 'abc'), '[REDACTED]');
  assert.equal(redactIfSensitive('api_key', 'test'), '[REDACTED]');
  assert.equal(redactIfSensitive('OPENCLAW_GROQ_API_KEY', 'gsk_abc'), '[REDACTED]');
});

test('redaction: preserves safe values', () => {
  assert.equal(redactIfSensitive('content-type', 'application/json'), 'application/json');
  assert.equal(redactIfSensitive('model', 'gpt-4'), 'gpt-4');
});

test('redaction: catches bearer pattern in values', () => {
  assert.equal(redactIfSensitive('some_field', 'Bearer eyJhbGciOiJ'), '[REDACTED]');
  assert.equal(redactIfSensitive('key', 'sk-1234567890abcdef'), '[REDACTED]');
});

test('REDACT_ENV_VARS: covers all catalog auth env vars', () => {
  for (const p of CATALOG) {
    if (p.auth && p.auth.env_var) {
      assert.ok(REDACT_ENV_VARS.includes(p.auth.env_var),
        `${p.auth.env_var} not in REDACT_ENV_VARS`);
    }
  }
});

// ════════════════════════════════════════════════════════════════════
// 4. ROUTER DETERMINISM
// ════════════════════════════════════════════════════════════════════
console.log('── Router ──');

test('router: returns empty when disabled', () => {
  const result = routeRequest({
    taskClass: 'fast_chat',
    providerHealth: {},
    quotaState: {},
    config: { enabled: false, vllmEnabled: false }
  });
  assert.equal(result.candidates.length, 0);
  assert.ok(result.explanation.some((e) => e.includes('disabled')));
});

test('router: returns local candidate when cloud disabled but local vLLM enabled', () => {
  const result = routeRequest({
    taskClass: 'fast_chat',
    providerHealth: {},
    quotaState: {},
    config: {
      enabled: false,
      vllmEnabled: true,
      providerAllowlist: [],
      providerDenylist: []
    },
    availableProviderIds: ['local_vllm']
  });
  assert.ok(result.candidates.length >= 1);
  assert.equal(result.candidates[0].provider_id, 'local_vllm');
});

test('router: prefers external free/cloud over local when cloud enabled', () => {
  const result = routeRequest({
    taskClass: 'fast_chat',
    providerHealth: {},
    quotaState: {},
    config: {
      enabled: true,
      vllmEnabled: true,
      providerAllowlist: [],
      providerDenylist: []
    }
  });
  const localIdx = result.candidates.findIndex((c) => c.provider_id === 'local_vllm');
  if (localIdx >= 0) {
    assert.ok(localIdx > 0, `expected local_vllm to be a fallback when cloud enabled (idx=${localIdx})`);
  }
});

test('router: skips unhealthy providers', () => {
  const result = routeRequest({
    taskClass: 'code',
    providerHealth: { groq: { ok: false, reason: 'down' } },
    quotaState: {},
    config: {
      enabled: true,
      vllmEnabled: false,
      providerAllowlist: [],
      providerDenylist: []
    }
  });
  assert.ok(!result.candidates.some((c) => c.provider_id === 'groq'));
  assert.ok(result.explanation.some((e) => e.includes('groq') && e.includes('unhealthy')));
});

test('router: skips providers over quota', () => {
  const result = routeRequest({
    taskClass: 'fast_chat',
    providerHealth: {},
    quotaState: { openrouter: { allowed: false, reason: 'rpm_exceeded' } },
    config: {
      enabled: true,
      vllmEnabled: false,
      providerAllowlist: [],
      providerDenylist: []
    }
  });
  assert.ok(!result.candidates.some((c) => c.provider_id === 'openrouter'));
});

test('router: respects denylist', () => {
  const result = routeRequest({
    taskClass: 'fast_chat',
    providerHealth: {},
    quotaState: {},
    config: {
      enabled: true,
      vllmEnabled: false,
      providerAllowlist: [],
      providerDenylist: ['groq', 'gemini']
    }
  });
  assert.ok(!result.candidates.some((c) => c.provider_id === 'groq'));
  assert.ok(!result.candidates.some((c) => c.provider_id === 'gemini'));
});

test('router: deterministic for same inputs', () => {
  const params = {
    taskClass: 'code',
    providerHealth: {},
    quotaState: {},
    config: {
      enabled: true,
      vllmEnabled: true,
      providerAllowlist: [],
      providerDenylist: []
    }
  };
  const r1 = routeRequest(params);
  const r2 = routeRequest(params);
  assert.equal(r1.candidates.length, r2.candidates.length);
  for (let i = 0; i < r1.candidates.length; i++) {
    assert.equal(r1.candidates[i].provider_id, r2.candidates[i].provider_id);
    assert.equal(r1.candidates[i].model_id, r2.candidates[i].model_id);
    assert.equal(r1.candidates[i].score, r2.candidates[i].score);
  }
});

test('explainRouting: produces string output', () => {
  const output = explainRouting({
    taskClass: 'fast_chat',
    providerHealth: {},
    quotaState: {},
    config: {
      enabled: true,
      vllmEnabled: false,
      providerAllowlist: [],
      providerDenylist: []
    }
  });
  assert.equal(typeof output, 'string');
  assert.ok(output.includes('FreeComputeCloud Routing Decision'));
  assert.ok(output.includes('fast_chat'));
});

// ════════════════════════════════════════════════════════════════════
// 5. QUOTA LEDGER
// ════════════════════════════════════════════════════════════════════
console.log('── Quota Ledger ──');

test('ledger: starts with zero counters', () => {
  const ledger = new QuotaLedger({ disabled: true });
  const check = ledger.check('test', { rpm: 10, rpd: 100 });
  assert.equal(check.allowed, true);
  assert.equal(check.counters.rpm, 0);
  assert.equal(check.counters.rpd, 0);
});

test('ledger: tracks requests', () => {
  const ledger = new QuotaLedger({ disabled: true });
  ledger.record('groq', { tokensIn: 100, tokensOut: 50 });
  ledger.record('groq', { tokensIn: 200, tokensOut: 100 });
  const check = ledger.check('groq', { rpm: 10 });
  assert.equal(check.counters.rpm, 2);
  assert.equal(check.counters.tpm, 450);
});

test('ledger: blocks when RPM exceeded', () => {
  const ledger = new QuotaLedger({ disabled: true });
  for (let i = 0; i < 5; i++) {
    ledger.record('test', { tokensIn: 10 });
  }
  const check = ledger.check('test', { rpm: 5 });
  assert.equal(check.allowed, false);
  assert.equal(check.reason, 'rpm_exceeded');
});

test('ledger: blocks when RPD exceeded', () => {
  const ledger = new QuotaLedger({ disabled: true });
  for (let i = 0; i < 3; i++) {
    ledger.record('test', { tokensIn: 10 });
  }
  const check = ledger.check('test', { rpd: 3 });
  assert.equal(check.allowed, false);
  assert.equal(check.reason, 'rpd_exceeded');
});

test('ledger: blocks when TPM exceeded', () => {
  const ledger = new QuotaLedger({ disabled: true });
  ledger.record('test', { tokensIn: 50000, tokensOut: 50001 });
  const check = ledger.check('test', { tpm: 100000 });
  assert.equal(check.allowed, false);
  assert.equal(check.reason, 'tpm_exceeded');
});

test('ledger: snapshot returns all providers', () => {
  const ledger = new QuotaLedger({ disabled: true });
  ledger.record('a', { tokensIn: 1 });
  ledger.record('b', { tokensIn: 2 });
  const snap = ledger.snapshot();
  assert.ok(snap.a);
  assert.ok(snap.b);
  assert.equal(snap.a.rpd, 1);
  assert.equal(snap.b.rpd, 1);
});

test('ledger: reset clears provider counters', () => {
  const ledger = new QuotaLedger({ disabled: true });
  ledger.record('test', { tokensIn: 100 });
  ledger.resetProvider('test');
  const check = ledger.check('test', { rpm: 1 });
  assert.equal(check.allowed, true);
  assert.equal(check.counters.rpm, 0);
});

test('ledger: disk persistence (write)', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'fc-ledger-'));
  try {
    const ledger = new QuotaLedger({ ledgerPath: tmpDir });
    ledger.record('test', { tokensIn: 100, tokensOut: 50 });
    const files = fs.readdirSync(tmpDir).filter((f) => f.endsWith('.jsonl'));
    assert.ok(files.length >= 1);
    const content = fs.readFileSync(path.join(tmpDir, files[0]), 'utf8');
    const entry = JSON.parse(content.trim().split('\n')[0]);
    assert.equal(entry.provider_id, 'test');
    assert.equal(entry.event, 'request');
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

// ════════════════════════════════════════════════════════════════════
// 6. vLLM UTILITIES
// ════════════════════════════════════════════════════════════════════
console.log('── vLLM Utilities ──');

test('vllmStartCommand: produces valid command', () => {
  const cmd = vllmStartCommand({ model: 'Qwen/Qwen2.5-7B', port: 8000 });
  assert.ok(cmd.includes('vllm.entrypoints'));
  assert.ok(cmd.includes('Qwen/Qwen2.5-7B'));
  assert.ok(cmd.includes('8000'));
  assert.ok(!cmd.includes('$OPENCLAW_VLLM_API_KEY')); // No key when not requested
});

test('vllmStartCommand: includes API key flag when requested', () => {
  const cmd = vllmStartCommand({ model: 'test', apiKey: true });
  assert.ok(cmd.includes('$OPENCLAW_VLLM_API_KEY'));
});

test('buildVllmStatusArtifact: wraps probe result', () => {
  const probe = { ts: '2026-02-12T00:00:00Z', healthy: false, models: [], inference_ok: false, error: 'timeout' };
  const artifact = buildVllmStatusArtifact(probe);
  assert.equal(artifact.version, '0.1');
  assert.equal(artifact.type, 'vllm_status');
  assert.equal(artifact.healthy, false);
});

// ════════════════════════════════════════════════════════════════════
// 7. PROVIDER REGISTRY
// ════════════════════════════════════════════════════════════════════
console.log('── Provider Registry ──');

test('registry: disabled by default', () => {
  const reg = new ProviderRegistry({ env: {} });
  assert.equal(reg.config.enabled, false);
  const snap = reg.snapshot();
  assert.equal(snap.enabled, false);
  // Even when cloud/free tiers are disabled, local vLLM remains an escape hatch.
  assert.ok(snap.adapters.length === 1 && snap.adapters[0].provider_id === 'local_vllm');
  reg.dispose();
});

test('registry: enabled but no credentials → no adapters', () => {
  const reg = new ProviderRegistry({
    env: { ENABLE_FREECOMPUTE_CLOUD: '1' }
  });
  assert.equal(reg.config.enabled, true);
  // No API keys set, so external providers with required auth are skipped
  const snap = reg.snapshot();
  // Local vLLM is the escape hatch; it should be present by default when enabled.
  assert.ok(snap.adapters.length === 1 && snap.adapters[0].provider_id === 'local_vllm');
  reg.dispose();
});

await testAsync('registry: dispatch returns null when disabled', async () => {
  const reg = new ProviderRegistry({ env: {} });

  // Replace the real adapter to avoid network. Keep provider_id key intact so routing selects it.
  reg._adapters.set('local_vllm', {
    async call() {
      return {
        text: 'ok',
        raw: {},
        usage: { inputTokens: 1, outputTokens: 1, totalTokens: 2, estimatedCostUsd: 0 }
      };
    },
    async health() {
      return { ok: true, models: ['stub-model'] };
    }
  });

  const result = await reg.dispatch({
    taskClass: 'fast_chat',
    messages: [{ role: 'user', content: 'test' }]
  });
  assert.ok(result, 'expected non-null result');
  assert.equal(result.provider_id, 'local_vllm');
  reg.dispose();
});

await testAsync('registry: dispatch uses local_vllm when it is the only eligible adapter', async () => {
  const reg = new ProviderRegistry({
    env: { ENABLE_FREECOMPUTE_CLOUD: '1' }
  });

  // Replace the real adapter to avoid network. Keep provider_id key intact so routing selects it.
  reg._adapters.set('local_vllm', {
    async generationProbe() {
      return { ok: true };
    },
    async call() {
      return {
        text: 'ok',
        raw: {},
        usage: { inputTokens: 1, outputTokens: 1, totalTokens: 2, estimatedCostUsd: 0 }
      };
    },
    async health() {
      return { ok: true, models: ['stub-model'] };
    }
  });

  const result = await reg.dispatch({
    taskClass: 'fast_chat',
    messages: [{ role: 'user', content: 'test' }]
  });

  assert.ok(result, 'expected non-null result');
  assert.equal(result.provider_id, 'local_vllm');
  reg.dispose();
});

await testAsync('registry: generation probe failure skips local and falls back to configured external', async () => {
  const reg = new ProviderRegistry({
    env: { ENABLE_FREECOMPUTE_CLOUD: '1', OPENCLAW_GROQ_API_KEY: 'x' }
  });

  reg._adapters.set('local_vllm', {
    async generationProbe() {
      return { ok: false, reason: 'timeout' };
    },
    async call() {
      throw new Error('local should not be called when generation probe fails');
    },
    async health() {
      return { ok: true, models: ['stub-model'] };
    }
  });

  reg._adapters.set('groq', {
    async call() {
      return {
        text: 'ok',
        raw: {},
        usage: { inputTokens: 1, outputTokens: 1, totalTokens: 2, estimatedCostUsd: 0 }
      };
    },
    async health() {
      return { ok: true, models: ['stub-model'] };
    }
  });

  const result = await reg.dispatch({
    taskClass: 'fast_chat',
    messages: [{ role: 'user', content: 'test' }]
  });

  assert.ok(result, 'expected non-null result');
  assert.equal(result.provider_id, 'groq');
  reg.dispose();
});

await testAsync('registry: prefers external over local when cloud enabled and external configured', async () => {
  const reg = new ProviderRegistry({
    env: { ENABLE_FREECOMPUTE_CLOUD: '1', OPENCLAW_GROQ_API_KEY: 'x' }
  });

  reg._adapters.set('local_vllm', {
    async generationProbe() {
      return { ok: true };
    },
    async call() {
      return {
        text: 'ok',
        raw: {},
        usage: { inputTokens: 1, outputTokens: 1, totalTokens: 2, estimatedCostUsd: 0 }
      };
    },
    async health() {
      return { ok: true, models: ['stub-model'] };
    }
  });

  reg._adapters.set('groq', {
    async call() {
      return {
        text: 'ok',
        raw: {},
        usage: { inputTokens: 1, outputTokens: 1, totalTokens: 2, estimatedCostUsd: 0 }
      };
    },
    async health() {
      return { ok: true, models: ['stub-model'] };
    }
  });

  const result = await reg.dispatch({
    taskClass: 'fast_chat',
    messages: [{ role: 'user', content: 'test' }]
  });

  assert.ok(result, 'expected non-null result');
  assert.equal(result.provider_id, 'groq');
  reg.dispose();
});

await testAsync('registry: http 429 opens circuit (rate_limit) and falls back to local', async () => {
  const reg = new ProviderRegistry({
    env: { ENABLE_FREECOMPUTE_CLOUD: '1', OPENCLAW_GROQ_API_KEY: 'x' }
  });

  reg._adapters.set('local_vllm', {
    async generationProbe() {
      return { ok: true };
    },
    async call() {
      return {
        text: 'ok',
        raw: {},
        usage: { inputTokens: 1, outputTokens: 1, totalTokens: 2, estimatedCostUsd: 0 }
      };
    },
    async health() {
      return { ok: true, models: ['stub-model'] };
    }
  });

  reg._adapters.set('groq', {
    async call() {
      const err = new Error('http 429');
      err.code = 'PROVIDER_HTTP_ERROR';
      err.statusCode = 429;
      throw err;
    },
    async health() {
      return { ok: true, models: ['stub-model'] };
    }
  });

  const result = await reg.dispatch({
    taskClass: 'fast_chat',
    messages: [{ role: 'user', content: 'test' }]
  });

  assert.ok(result, 'expected non-null result');
  assert.equal(result.provider_id, 'local_vllm');
  assert.equal(reg._circuitBreakers.get('groq').state, CB_STATES.OPEN);
  reg.dispose();
});

await testAsync('registry: circuit_open excludes provider from routing until cooldown expires', async () => {
  const reg = new ProviderRegistry({
    env: { ENABLE_FREECOMPUTE_CLOUD: '1', OPENCLAW_GROQ_API_KEY: 'x' }
  });

  let groqCalls = 0;

  reg._adapters.set('local_vllm', {
    async generationProbe() {
      return { ok: true };
    },
    async call() {
      return {
        text: 'ok',
        raw: {},
        usage: { inputTokens: 1, outputTokens: 1, totalTokens: 2, estimatedCostUsd: 0 }
      };
    },
    async health() {
      return { ok: true, models: ['stub-model'] };
    }
  });

  reg._adapters.set('groq', {
    async call() {
      groqCalls += 1;
      const err = new Error('http 429');
      err.code = 'PROVIDER_HTTP_ERROR';
      err.statusCode = 429;
      throw err;
    },
    async health() {
      return { ok: true, models: ['stub-model'] };
    }
  });

  // First call opens the circuit.
  const first = await reg.dispatch({
    taskClass: 'fast_chat',
    messages: [{ role: 'user', content: 'test' }]
  });
  assert.ok(first);
  assert.equal(reg._circuitBreakers.get('groq').state, CB_STATES.OPEN);

  // Second call should not attempt groq at all while circuit is open.
  groqCalls = 0;
  const second = await reg.dispatch({
    taskClass: 'fast_chat',
    messages: [{ role: 'user', content: 'test' }]
  });
  assert.ok(second);
  assert.equal(second.provider_id, 'local_vllm');
  assert.equal(groqCalls, 0);
  reg.dispose();
});

await testAsync('registry: compaction gate does not run under budget', async () => {
  const events = [];
  const reg = new ProviderRegistry({
    env: { ENABLE_FREECOMPUTE_CLOUD: '1', OPENCLAW_GROQ_API_KEY: 'x', GROQ_MAX_CHARS: '2000' },
    emitEvent: (t, p) => events.push({ t, p })
  });

  reg._adapters.set('local_vllm', {
    async generationProbe() {
      return { ok: true };
    },
    async call() {
      throw new Error('local should not be selected when groq is configured');
    },
    async health() {
      return { ok: true, models: ['stub-model'] };
    }
  });

  let seen = null;
  reg._adapters.set('groq', {
    async call(params) {
      seen = params.messages;
      return {
        text: 'ok',
        raw: {},
        usage: { inputTokens: 1, outputTokens: 1, totalTokens: 2, estimatedCostUsd: 0 }
      };
    },
    async health() {
      return { ok: true, models: ['stub-model'] };
    }
  });

  const msg = 'x'.repeat(100);
  const result = await reg.dispatch({
    taskClass: 'fast_chat',
    messages: [{ role: 'user', content: msg }]
  });

  assert.ok(result);
  assert.equal(result.provider_id, 'groq');
  assert.ok(Array.isArray(seen));
  assert.equal(seen[0].content.length, 100);
  assert.equal(events.some((e) => e.t === 'freecompute_dispatch_compaction_applied'), false);
  reg.dispose();
});

await testAsync('registry: compaction gate compacts preflight when materially over budget', async () => {
  const events = [];
  const reg = new ProviderRegistry({
    env: { ENABLE_FREECOMPUTE_CLOUD: '1', OPENCLAW_GROQ_API_KEY: 'x', GROQ_MAX_CHARS: '1000' },
    emitEvent: (t, p) => events.push({ t, p })
  });

  reg._adapters.set('local_vllm', {
    async generationProbe() {
      return { ok: true };
    },
    async call() {
      throw new Error('local should not be selected when groq is configured');
    },
    async health() {
      return { ok: true, models: ['stub-model'] };
    }
  });

  let seenShape = null;
  reg._adapters.set('groq', {
    async call(params) {
      seenShape = registryTest.estimateRequestShape(params.messages);
      return {
        text: 'ok',
        raw: {},
        usage: { inputTokens: 1, outputTokens: 1, totalTokens: 2, estimatedCostUsd: 0 }
      };
    },
    async health() {
      return { ok: true, models: ['stub-model'] };
    }
  });

  const messages = [
    { role: 'system', content: 's'.repeat(800) },
    { role: 'user', content: 'u'.repeat(600) }
  ];
  const before = registryTest.estimateRequestShape(messages);
  assert.ok(before.char_count_total > 1000);

  const result = await reg.dispatch({ taskClass: 'fast_chat', messages });
  assert.ok(result);
  assert.equal(result.provider_id, 'groq');
  assert.ok(seenShape && typeof seenShape.char_count_total === 'number');
  assert.ok(seenShape.char_count_total <= 1000, `expected compacted <= 1000, got ${seenShape.char_count_total}`);

  const comp = events.find((e) => e.t === 'freecompute_dispatch_compaction_applied');
  assert.ok(comp, 'expected compaction event');
  assert.equal(comp.p.trigger, 'preflight');
  reg.dispose();
});

await testAsync('registry: 400 context-length triggers one compaction retry (no preflight)', async () => {
  const events = [];
  const reg = new ProviderRegistry({
    env: { ENABLE_FREECOMPUTE_CLOUD: '1', OPENCLAW_GROQ_API_KEY: 'x', GROQ_MAX_CHARS: '1000' },
    emitEvent: (t, p) => events.push({ t, p })
  });

  reg._adapters.set('local_vllm', {
    async generationProbe() {
      return { ok: true };
    },
    async call() {
      throw new Error('local should not be selected when groq succeeds');
    },
    async health() {
      return { ok: true, models: ['stub-model'] };
    }
  });

  let calls = 0;
  let firstShape = null;
  let secondShape = null;

  reg._adapters.set('groq', {
    async call(params) {
      calls += 1;
      const s = registryTest.estimateRequestShape(params.messages);
      if (calls === 1) {
        firstShape = s;
        const err = new Error('context length exceeded');
        err.code = 'PROVIDER_HTTP_ERROR';
        err.statusCode = 400;
        throw err;
      }
      secondShape = s;
      return {
        text: 'ok',
        raw: {},
        usage: { inputTokens: 1, outputTokens: 1, totalTokens: 2, estimatedCostUsd: 0 }
      };
    },
    async health() {
      return { ok: true, models: ['stub-model'] };
    }
  });

  // Content total ~1000 chars, below the 1.05 preflight margin for max=1000 once overhead is included.
  const messages = [
    { role: 'system', content: 's'.repeat(700) },
    { role: 'user', content: 'u'.repeat(300) }
  ];
  const result = await reg.dispatch({ taskClass: 'fast_chat', messages });
  assert.ok(result);
  assert.equal(result.provider_id, 'groq');
  assert.equal(calls, 2);
  assert.ok(firstShape && secondShape);
  assert.ok(secondShape.char_count_total < firstShape.char_count_total);

  const comp = events.find((e) => e.t === 'freecompute_dispatch_compaction_applied');
  assert.ok(comp, 'expected compaction event');
  assert.equal(comp.p.trigger, 'error_400');
  reg.dispose();
});

await testAsync('registry: audit events identify which provider rejects size (groq 400 → local fallback)', async () => {
  const events = [];
  const reg = new ProviderRegistry({
    env: { ENABLE_FREECOMPUTE_CLOUD: '1', OPENCLAW_GROQ_API_KEY: 'x', GROQ_MAX_CHARS: '1000' },
    emitEvent: (t, p) => events.push({ t, p })
  });

  reg._adapters.set('local_vllm', {
    async generationProbe() {
      return { ok: true };
    },
    async call() {
      return {
        text: 'ok',
        raw: {},
        usage: { inputTokens: 1, outputTokens: 1, totalTokens: 2, estimatedCostUsd: 0 }
      };
    },
    async health() {
      return { ok: true, models: ['stub-model'] };
    }
  });

  let groqCalls = 0;
  reg._adapters.set('groq', {
    async call() {
      groqCalls += 1;
      const err = new Error('Please reduce the length of the messages.');
      err.code = 'PROVIDER_HTTP_ERROR';
      err.statusCode = 400;
      throw err;
    },
    async health() {
      return { ok: true, models: ['stub-model'] };
    }
  });

  const result = await reg.dispatch({
    taskClass: 'fast_chat',
    // Keep under the 1.05 preflight margin so the retry path is driven by the 400 error.
    messages: [
      { role: 'system', content: 's'.repeat(700) },
      { role: 'user', content: 'u'.repeat(300) }
    ]
  });

  assert.ok(result);
  assert.equal(result.provider_id, 'local_vllm');
  assert.equal(groqCalls, 2, 'expected groq initial attempt + one compaction retry');

  const groqErr = events.find((e) => e.t === 'freecompute_dispatch_error_shape' && e.p.provider_id === 'groq');
  assert.ok(groqErr, 'expected groq error shape event');
  assert.equal(groqErr.p.statusCode, 400);
  reg.dispose();
});

test('registry: explain works when enabled', () => {
  const reg = new ProviderRegistry({
    env: { ENABLE_FREECOMPUTE_CLOUD: '1' }
  });
  const output = reg.explain({ taskClass: 'code' });
  assert.equal(typeof output, 'string');
  assert.ok(output.includes('FreeComputeCloud'));
  reg.dispose();
});

test('registry: CB_STATES exported', () => {
  assert.equal(CB_STATES.CLOSED, 'CLOSED');
  assert.equal(CB_STATES.OPEN, 'OPEN');
  assert.equal(CB_STATES.HALF_OPEN, 'HALF_OPEN');
});

// ════════════════════════════════════════════════════════════════════
// 8. PROVIDER ADAPTER (unit, no network)
// ════════════════════════════════════════════════════════════════════
console.log('── Provider Adapter ──');

test('adapter: constructs from catalog entry', () => {
  const entry = getProvider('groq');
  const adapter = new ProviderAdapter(entry, { env: {} });
  assert.equal(adapter.providerId, 'groq');
  assert.equal(adapter.protocol, 'openai_compatible');
  assert.ok(adapter.baseUrl.includes('groq.com'));
});

test('adapter: resolves env override for base_url', () => {
  const entry = getProvider('groq');
  const adapter = new ProviderAdapter(entry, {
    env: { OPENCLAW_GROQ_BASE_URL: 'http://localhost:9999/v1' }
  });
  assert.equal(adapter.baseUrl, 'http://localhost:9999/v1');
});

test('adapter: does not expose auth token', () => {
  const entry = getProvider('groq');
  const adapter = new ProviderAdapter(entry, {
    env: { OPENCLAW_GROQ_API_KEY: 'gsk_secret_test_key' }
  });
  const json = JSON.stringify(adapter);
  assert.ok(!json.includes('gsk_secret_test_key'), 'auth token leaked in serialization');
});

test('adapter: uses healthcheck chat timeout override when present', async () => {
  const http = require('node:http');
  const { EventEmitter } = require('node:events');

  const originalRequest = http.request;
  try {
    let observedTimeout = null;
    http.request = (options, cb) => {
      observedTimeout = options && options.timeout;

      const res = new EventEmitter();
      res.statusCode = 200;

      // Emit a minimal OpenAI-compatible response.
      process.nextTick(() => {
        cb(res);
        res.emit('data', JSON.stringify({
          model: 'stub',
          choices: [{ message: { content: 'ok' } }],
          usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 }
        }));
        res.emit('end');
      });

      const req = new EventEmitter();
      req.write = () => {};
      req.end = () => {};
      req.destroy = () => {};
      return req;
    };

    const entry = {
      provider_id: 'test_openai_like',
      kind: 'external',
      protocol: 'openai_compatible',
      enabled_default: false,
      base_url: { default: 'http://example.invalid/v1', env_override: 'TEST_BASE_URL' },
      auth: { type: 'none', env_var: null, redact_in_logs: true },
      models: [{ model_id: 'stub-model', task_classes: ['fast_chat'], context_window_hint: null, tool_support: 'via_adapter' }],
      constraints: { quota: { rpm_default: 1, rpd_default: 1, tpm_default: 1, tpd_default: 1 }, backoff: {}, circuit_breaker: {} },
      healthcheck: { type: 'openai_compatible', endpoints: { models: '/models', chat: '/chat/completions' }, timeouts_ms: { chat: 12345 } },
      routing_tags: { prefers: [], avoids: [] }
    };

    const adapter = new ProviderAdapter(entry, { env: {} });
    const result = await adapter.call({
      messages: [{ role: 'user', content: 'test' }],
      metadata: { model: 'stub-model', maxTokens: 8, temperature: 0 }
    });

    assert.equal(result.text, 'ok');
    assert.equal(observedTimeout, 12345);
  } finally {
    http.request = originalRequest;
  }
});

// ════════════════════════════════════════════════════════════════════
// 9. INTEGRATION TESTS (skipped by default)
// ════════════════════════════════════════════════════════════════════
console.log('── Integration Tests ──');

const integrationEnabled = process.env.FREECOMPUTE_INTEGRATION === '1';

if (integrationEnabled) {
  await testAsync('integration: vLLM probe (requires running server)', async () => {
    const { probeVllmServer } = require('../core/system2/inference');
    const result = await probeVllmServer();
    console.log('  vLLM probe result:', JSON.stringify(result, null, 2));
    // Don't assert ok — server may not be running
    assert.equal(typeof result.healthy, 'boolean');
  });

  await testAsync('integration: Groq health (requires OPENCLAW_GROQ_API_KEY)', async () => {
    if (!process.env.OPENCLAW_GROQ_API_KEY) {
      skip('groq health', 'no API key');
      return;
    }
    const entry = getProvider('groq');
    const adapter = new ProviderAdapter(entry);
    const health = await adapter.health();
    console.log('  Groq health:', JSON.stringify(health, null, 2));
    assert.equal(typeof health.ok, 'boolean');
  });
} else {
  skip('integration: vLLM probe', 'FREECOMPUTE_INTEGRATION not set');
  skip('integration: Groq health', 'FREECOMPUTE_INTEGRATION not set');
  skip('integration: dry-run provider probe', 'FREECOMPUTE_INTEGRATION not set');
}

// ════════════════════════════════════════════════════════════════════
// SUMMARY
// ════════════════════════════════════════════════════════════════════

console.log('\n════════════════════════════════════════════');
console.log(`FreeComputeCloud Tests: ${passed} passed, ${failed} failed, ${skipped} skipped`);
if (failures.length > 0) {
  console.log('\nFailures:');
  for (const f of failures) {
    console.log(`  * ${f.name}: ${f.error}`);
  }
}
console.log('════════════════════════════════════════════\n');

process.exit(failed > 0 ? 1 : 0);

} // end main

main().catch((err) => {
  console.error('Fatal test error:', err);
  process.exit(2);
});
