#!/usr/bin/env node
'use strict';

async function main() {
  const fallback = Number.parseInt(process.env.VLLM_MAX_SEQS || '16', 10) || 16;
  let ConcurrencyTuner = null;
  try {
    ({ ConcurrencyTuner } = require('../core/system2/inference/concurrency_tuner'));
  } catch (_err) {
    process.stdout.write(String(fallback));
    return;
  }
  const tuner = new ConcurrencyTuner({ maxConcurrency: fallback });
  const recommendation = await tuner.update();
  const safe = Number.isFinite(recommendation) ? recommendation : fallback;
  process.stdout.write(String(safe));
}

main().catch((err) => {
  process.stderr.write(`[tune_concurrency] failed: ${err && err.message ? err.message : String(err)}\n`);
  process.exit(1);
});
