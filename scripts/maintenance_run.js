#!/usr/bin/env node
'use strict';

const { runAll, runQuickFix, listQuickFixes } = require('../sys/maintenance');

function main() {
  const mode = process.argv.includes('--check') ? 'check' : 'all';
  const nameArg = process.argv.find((arg) => arg.startsWith('--name='));

  if (mode === 'check') {
    console.log(
      JSON.stringify(
        {
          quickFixes: listQuickFixes(),
          count: listQuickFixes().length
        },
        null,
        2
      )
    );
    return;
  }

  if (nameArg) {
    const name = nameArg.split('=')[1];
    const result = runQuickFix(name, {});
    console.log(JSON.stringify({ name, result }, null, 2));
    return;
  }

  const output = runAll({ markdown: 'See [link](docs/evolution_2026-02.md)' });
  console.log(JSON.stringify({ ran: output.length, output }, null, 2));
}

main();
