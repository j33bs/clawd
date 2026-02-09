#!/usr/bin/env node
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const sys = require('../sys');

const config = sys.config.loadConfig();
const maintenance = sys.maintenance.listQuickFixes();
const breath = sys.breath.summary();

console.log('SYSTEM_EVOLUTION_SAMPLE_RUN');
console.log(`project_root=${process.cwd()}`);
console.log(`featureFlags=${JSON.stringify(config.featureFlags)}`);
console.log(`quickFixes=${maintenance.length}`);
console.log(`breath_status=${breath.status}`);
console.log('note=scaffold run complete');
