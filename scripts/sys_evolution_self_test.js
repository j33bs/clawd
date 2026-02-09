#!/usr/bin/env node
'use strict';

const { execFileSync } = require('node:child_process');

const commands = [
  ['node', ['tests/sys_config.test.js']],
  ['node', ['tests/sys_memory_graph.test.js']],
  ['node', ['tests/sys_render.test.js']],
  ['node', ['tests/sys_scheduler.test.js']],
  ['node', ['tests/sys_maintenance.test.js']],
  ['node', ['tests/sys_breath_knowledge.test.js']],
  ['node', ['tests/sys_legacy_bridge.test.js']],
  ['node', ['tests/sys_acceptance.test.js']],
  ['node', ['scripts/sys_evolution_sample_run.mjs']]
];

if (process.env.OPENCLAW_AUDIT_LOGGING === '1') {
  commands.push(['node', ['scripts/audit_snapshot.mjs']]);
  commands.push(['node', ['scripts/audit_verify.mjs']]);
}

commands.forEach(([bin, args]) => {
  const label = `${bin} ${args.join(' ')}`;
  execFileSync(bin, args, { stdio: 'inherit' });
  console.log(`PASS ${label}`);
});

console.log('SYSTEM_EVOLUTION_SELF_TEST=PASS');
