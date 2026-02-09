const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { createQueueStore, createScheduler, plusSeconds } = require('../sys/scheduler');
const { createMemoryGraphStore } = require('../sys/memory_graph');

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

run('queue store persists tasks and next_allowed_time', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sys-queue-test-'));
  const queue = createQueueStore({ dbPath: path.join(tmpDir, 'queue.sqlite') });

  const taskId = queue.enqueueTask({
    name: 'brief task',
    persona_path: path.join(process.cwd(), 'sys', 'specialists', 'brief_summariser', 'persona.json'),
    interval_seconds: 120,
    next_allowed_time: '2026-02-09T00:00:00.000Z'
  });

  const tasks = queue.listTasks();
  assert.strictEqual(tasks.length, 1);
  assert.strictEqual(tasks[0].id, taskId);

  queue.updateTaskSchedule(taskId, '2026-02-09T00:02:00.000Z', '2026-02-09T00:00:30.000Z');
  const updated = queue.listTasks()[0];
  assert.strictEqual(updated.next_allowed_time, '2026-02-09T00:02:00.000Z');

  queue.close();
});

run('scheduler executes runnable specialist and writes output', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sys-scheduler-run-'));
  const queue = createQueueStore({ dbPath: path.join(tmpDir, 'queue.sqlite') });
  const graph = createMemoryGraphStore({ storagePath: path.join(tmpDir, 'memory_graph.jsonld') });
  const scheduler = createScheduler({
    queueStore: queue,
    outputDir: path.join(tmpDir, 'outputs'),
    graphStore: graph
  });

  scheduler.enqueue({
    name: 'brief_summariser',
    persona_path: path.join(process.cwd(), 'sys', 'specialists', 'brief_summariser', 'persona.json'),
    interval_seconds: 300,
    next_allowed_time: '2026-02-09T00:00:00.000Z'
  });

  const result = scheduler.runOnce('2026-02-09T00:00:01.000Z');
  assert.strictEqual(result.ran, 1);
  assert.strictEqual(result.outputs[0].status, 'ok');
  assert.ok(fs.existsSync(result.outputs[0].outputPath));

  const runs = queue.listRuns();
  assert.strictEqual(runs.length, 1);
  assert.strictEqual(runs[0].status, 'ok');

  const tasks = queue.listTasks();
  assert.strictEqual(tasks.length, 1);
  assert.ok(tasks[0].next_allowed_time > '2026-02-09T00:00:01.000Z');

  const graphExport = graph.exportGraph();
  const runNodes = graphExport['@graph'].filter((entry) => entry['@type'] === 'Run');
  assert.strictEqual(runNodes.length, 1);

  queue.close();
});

run('plusSeconds helper is deterministic', () => {
  const next = plusSeconds('2026-02-09T00:00:00.000Z', 60);
  assert.strictEqual(next, '2026-02-09T00:01:00.000Z');
});
