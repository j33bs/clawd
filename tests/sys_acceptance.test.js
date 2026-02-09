const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { loadConfig, watchConfig } = require('../sys/config');
const { createMemoryGraphStore } = require('../sys/memory_graph');
const { render } = require('../sys/render');
const { createQueueStore, createScheduler } = require('../sys/scheduler');
const { enqueueMaintenanceTasks, runAll } = require('../sys/maintenance');

function pass(name) {
  console.log(`PASS ${name}`);
}

function fail(name, error) {
  console.error(`FAIL ${name}`);
  console.error(error.message);
  process.exit(1);
}

function testSemanticQuery() {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'accept-graph-'));
  const graph = createMemoryGraphStore({ storagePath: path.join(tmpDir, 'graph.jsonld') });
  graph.upsertNode({ '@id': 'concept:breathwork', '@type': 'Concept', title: 'breathwork', tags: ['breathwork'] });
  graph.upsertNode({ '@id': 'concept:coherence', '@type': 'Concept', title: 'coherence', tags: ['coherence'] });
  graph.addRelation('concept:breathwork', 'concept:coherence', 'extends');

  const related = graph.fetchRelated('breathwork', 2);
  assert.ok(related.nodes.length >= 2);
  pass('semantic query fetch_related("breathwork",2)');
}

function testTemplateRender() {
  const rendered = render({
    template: 'brief',
    format: 'html',
    templatesDir: path.join(process.cwd(), 'sys', 'templates'),
    data: {
      title: 'Acceptance Brief',
      date: '2026-02-09',
      summary: 'render test',
      highlights: { first: 'one', second: 'two' },
      notes: 'done'
    }
  });
  assert.ok(rendered.output.includes('<h1>Acceptance Brief</h1>'));
  pass('template render pipeline');
}

async function testConfigHotReloadTrace() {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'accept-config-'));
  const configPath = path.join(tmpDir, 'config.toml');
  fs.copyFileSync(path.join(process.cwd(), 'sys', 'config.toml'), configPath);

  await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      cleanup();
      reject(new Error('hot reload trace not emitted'));
    }, 1500);

    const cleanup = watchConfig({
      configPath,
      onReload(event) {
        clearTimeout(timeout);
        cleanup();
        if (event.type !== 'config_hot_reload') {
          reject(new Error('unexpected event type'));
          return;
        }
        resolve();
      },
      onError(error) {
        clearTimeout(timeout);
        cleanup();
        reject(error);
      }
    });

    setTimeout(() => {
      const next = fs.readFileSync(configPath, 'utf8').replace('tick_seconds = 300', 'tick_seconds = 301');
      fs.writeFileSync(configPath, next, 'utf8');
    }, 100);
  });

  pass('config hot reload trace');
}

function testSchedulerAndMaintenance() {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'accept-scheduler-'));
  const queue = createQueueStore({ dbPath: path.join(tmpDir, 'queue.sqlite') });
  const scheduler = createScheduler({ queueStore: queue, outputDir: path.join(tmpDir, 'outputs') });

  scheduler.enqueue({
    name: 'brief_summariser',
    persona_path: path.join(process.cwd(), 'sys', 'specialists', 'brief_summariser', 'persona.json'),
    interval_seconds: 120,
    next_allowed_time: '2026-02-09T00:00:00.000Z'
  });

  const runResult = scheduler.runOnce('2026-02-09T00:00:10.000Z');
  assert.strictEqual(runResult.ran, 1);
  assert.ok(queue.listTasks()[0].next_allowed_time > '2026-02-09T00:00:10.000Z');

  const maintenanceIds = enqueueMaintenanceTasks(queue, {
    intervalSeconds: 900,
    personaPath: path.join(process.cwd(), 'sys', 'specialists', 'maintenance_runner', 'persona.json')
  });
  assert.strictEqual(maintenanceIds.length, 10);

  const maintenanceRun = runAll({ markdown: 'see [docs](docs/evolution_2026-02.md)' });
  assert.strictEqual(maintenanceRun.length, 10);

  queue.close();
  pass('scheduler + maintenance checks');
}

async function main() {
  try {
    loadConfig({ configPath: path.join(process.cwd(), 'sys', 'config.toml') });
    testSemanticQuery();
    testTemplateRender();
    await testConfigHotReloadTrace();
    testSchedulerAndMaintenance();
  } catch (error) {
    fail('acceptance suite', error);
  }
}

main();
