#!/usr/bin/env node
'use strict';

/**
 * vLLM Server Probe Script
 *
 * Probes a local vLLM server and outputs a status artifact.
 *
 * Usage:
 *   node scripts/vllm_probe.js [--json] [--url <base_url>]
 *
 * Environment:
 *   OPENCLAW_VLLM_BASE_URL  - Override base URL
 *   OPENCLAW_VLLM_API_KEY   - Optional API key (never printed)
 *
 * Output: JSON status artifact to stdout (--json) or human-readable.
 */

const { probeVllmServer, vllmStartCommand, buildVllmStatusArtifact } = require('../core/system2/inference/vllm_provider');

async function main() {
  const args = process.argv.slice(2);
  const jsonMode = args.includes('--json');
  const urlIdx = args.indexOf('--url');
  const baseUrl = urlIdx !== -1 ? args[urlIdx + 1] : undefined;
  const dryRun = args.includes('--dry-run');

  if (dryRun) {
    console.log('=== vLLM Start Command (dry-run) ===\n');
    console.log(vllmStartCommand({
      model: process.env.OPENCLAW_VLLM_MODEL || '<MODEL_NAME>',
      port: Number(process.env.OPENCLAW_VLLM_PORT || 8000),
      apiKey: Boolean(process.env.OPENCLAW_VLLM_API_KEY)
    }));
    console.log('\n(No execution performed. Set env vars and run manually.)');
    return;
  }

  const result = await probeVllmServer({ baseUrl });
  const artifact = buildVllmStatusArtifact(result);

  if (jsonMode) {
    console.log(JSON.stringify(artifact, null, 2));
  } else {
    console.log('=== vLLM Server Probe ===');
    console.log(`URL:           ${result.base_url}`);
    console.log(`Healthy:       ${result.healthy}`);
    console.log(`Models:        ${result.models.length > 0 ? result.models.join(', ') : '(none)'}`);
    console.log(`Inference OK:  ${result.inference_ok}`);
    if (result.error) {
      console.log(`Error:         ${result.error}`);
    }
    console.log(`Timestamp:     ${result.ts}`);
  }

  process.exit(result.healthy ? 0 : 1);
}

main().catch((err) => {
  console.error('Fatal:', err.message);
  process.exit(2);
});
