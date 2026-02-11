#!/usr/bin/env node
'use strict';

const { loadConfig } = require('../sys/config');
const { probeStartupInvariants } = require('../core/system2/startup_invariants');

function main() {
  try {
    const config = loadConfig();
    const report = probeStartupInvariants({
      config,
      workspaceRoot: process.cwd()
    });
    console.log(JSON.stringify(report, null, 2));
    if (!report.ok) {
      process.exit(1);
    }
  } catch (error) {
    console.log(
      JSON.stringify(
        {
          ok: false,
          checked_at: new Date().toISOString(),
          error: error && error.message ? error.message : String(error)
        },
        null,
        2
      )
    );
    process.exit(2);
  }
}

main();
