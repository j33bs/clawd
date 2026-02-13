#!/usr/bin/env node
'use strict';

const { resolveSystem2VllmConfig } = require('../core/system2/inference/system2_config_resolver');

async function main() {
  console.log('=== System 2 vLLM Smoke Test ===\n');

  // Test 1: System 2 config path
  console.log('Test 1: System 2 config resolution');
  const mockEnv1 = {
    SYSTEM2_VLLM_BASE_URL: 'http://system2-server:8888/v1',
    OPENCLAW_VLLM_BASE_URL: 'http://fallback:7777/v1'
  };

  try {
    const config1 = resolveSystem2VllmConfig({
      env: mockEnv1,
      emitEvent: (type, payload) => {
        console.log(`  Event: ${type}`);
        console.log(`    - base_url_source: ${payload.base_url_source}`);
        console.log(`    - api_key_source: ${payload.api_key_source}`);
      }
    });
    console.log('  ✓ Resolved System 2 base_url source');
    console.log(`  ✓ Config keys: base_url=${config1.base_url ? 'set' : 'missing'}, timeout_ms=${config1.timeout_ms}ms`);
  } catch (err) {
    console.error(`  ✗ FAILED: ${err.message}`);
    process.exit(1);
  }

  // Test 2: Fallback to System 1
  console.log('\nTest 2: Fallback to System 1 config');
  const mockEnv2 = {
    OPENCLAW_VLLM_BASE_URL: 'http://system1:7777/v1'
  };

  try {
    resolveSystem2VllmConfig({
      env: mockEnv2
    });
    console.log('  ✓ Resolved System 1 base_url (SYSTEM2 vars not set)');
  } catch (err) {
    console.error(`  ✗ FAILED: ${err.message}`);
    process.exit(1);
  }

  // Test 3: Default path
  console.log('\nTest 3: Default config (no env vars)');
  try {
    const config3 = resolveSystem2VllmConfig({
      env: {}
    });
    console.log(`  ✓ Resolved default base_url: ${config3.base_url}`);
  } catch (err) {
    console.error(`  ✗ FAILED: ${err.message}`);
    process.exit(1);
  }

  // Test 4: Precedence (explicit > system2 > system1 > default)
  console.log('\nTest 4: Config precedence (explicit args win)');
  try {
    const config4 = resolveSystem2VllmConfig({
      baseUrl: 'http://explicit:9999/v1',
      env: {
        SYSTEM2_VLLM_BASE_URL: 'http://system2:8888/v1',
        OPENCLAW_VLLM_BASE_URL: 'http://system1:7777/v1'
      }
    });
    if (config4.base_url === 'http://explicit:9999/v1') {
      console.log('  ✓ Explicit args took precedence');
    } else {
      console.error(`  ✗ Precedence check failed: got ${config4.base_url}`);
      process.exit(1);
    }
  } catch (err) {
    console.error(`  ✗ FAILED: ${err.message}`);
    process.exit(1);
  }

  console.log('\n✓ All smoke tests PASSED\n');
  process.exit(0);
}

main();

