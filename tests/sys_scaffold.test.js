const assert = require('node:assert');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

const sys = require('../sys');

function run(name, fn) {
  try {
    fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    console.error(error.message);
    process.exit(1);
  }
}

run('sys exports load', () => {
  assert.ok(sys.config);
  assert.ok(sys.memoryGraph);
  assert.ok(sys.render);
  assert.ok(sys.scheduler);
  assert.ok(sys.maintenance);
  assert.ok(sys.breath);
});

run('breath summary scaffold is evidence-safe', () => {
  const payload = sys.breath.summary();
  assert.strictEqual(payload.status, 'no_ingested_sources');
  assert.ok(Array.isArray(payload.items));
  assert.strictEqual(payload.items.length, 0);
});

run('sample run script executes', () => {
  const scriptPath = path.join(__dirname, '..', 'scripts', 'sys_evolution_sample_run.mjs');
  const output = execFileSync('node', [scriptPath], { encoding: 'utf8' });
  assert.ok(output.includes('SYSTEM_EVOLUTION_SAMPLE_RUN'));
  assert.ok(output.includes('breath_status=no_ingested_sources'));
});
