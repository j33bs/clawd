const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const {
  listQuickFixes,
  runAll,
  runQuickFix,
  enqueueMaintenanceTasks
} = require('../sys/maintenance');
const { createQueueStore } = require('../sys/scheduler');

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

run('maintenance registry exposes 10 quick fixes', () => {
  const fixes = listQuickFixes();
  assert.strictEqual(fixes.length, 10);
});

run('maintenance dry-run executes all checks', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sys-maintenance-'));
  const result = runAll({
    markdown: 'See [docs](docs/evolution_2026-02.md)',
    logDir: tmpDir
  });

  assert.strictEqual(result.length, 10);
  assert.ok(result.every((entry) => entry.status === 'ok'));
});

run('enqueueMaintenanceTasks integrates with scheduler queue', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sys-maintenance-queue-'));
  const queue = createQueueStore({ dbPath: path.join(tmpDir, 'queue.sqlite') });

  const insertedIds = enqueueMaintenanceTasks(queue, {
    intervalSeconds: 600,
    personaPath: path.join(process.cwd(), 'sys', 'specialists', 'maintenance_runner', 'persona.json')
  });

  assert.strictEqual(insertedIds.length, 10);
  assert.strictEqual(queue.listTasks().length, 10);

  const single = runQuickFix('date_aware_brief_namer', { now: '2026-02-09T00:00:00.000Z' });
  assert.ok(single.fileName.startsWith('2026-02-09-'));

  queue.close();
});
