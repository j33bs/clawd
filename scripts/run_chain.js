#!/usr/bin/env node

const { runChain } = require('../core/chain/chain_runner');

async function main() {
  const input = process.argv.slice(2).join(' ').trim();
  if (!input) {
    console.error('Usage: node scripts/run_chain.js "<request>"');
    process.exit(1);
  }

  const state = await runChain(input, {});
  console.log(state.outputs.finalText || 'No output generated.');
}

main().catch((error) => {
  console.error('FAIL run_chain');
  console.error(`  ${error.message}`);
  process.exit(1);
});
