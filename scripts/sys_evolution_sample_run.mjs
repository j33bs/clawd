#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { loadConfig, watchConfig } = require('../sys/config');
const { createMemoryGraphStore } = require('../sys/memory_graph');
const { render } = require('../sys/render');
const { createQueueStore, createScheduler } = require('../sys/scheduler');
const { enqueueMaintenanceTasks } = require('../sys/maintenance');
const { appendMigrationLog } = require('../sys/utils/migration_log');
const breath = require('../sys/knowledge/breath');

function waitForHotReload(configPath) {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      cleanup();
      reject(new Error('config hot reload trace timeout'));
    }, 2000);

    const cleanup = watchConfig({
      configPath,
      onReload(event) {
        clearTimeout(timeout);
        cleanup();
        resolve(event);
      },
      onError(error) {
        clearTimeout(timeout);
        cleanup();
        reject(error);
      }
    });

    setTimeout(() => {
      const next = fs.readFileSync(configPath, 'utf8').replace('tick_seconds = 300', 'tick_seconds = 305');
      fs.writeFileSync(configPath, next, 'utf8');
    }, 100);
  });
}

async function main() {
  const projectRoot = process.cwd();
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sys-evolution-sample-'));
  const configPath = path.join(tmpDir, 'config.toml');
  fs.copyFileSync(path.join(projectRoot, 'sys', 'config.toml'), configPath);
  appendMigrationLog({ phase: 'sample_run_start', projectRoot, configPath });

  const config = loadConfig({
    configPath,
    env: {
      SYS__FEATURE_FLAGS__SYSTEM_EVOLUTION_ENABLED: 'true'
    }
  });

  const graphStore = createMemoryGraphStore({ storagePath: path.join(tmpDir, 'memory_graph.jsonld') });
  graphStore.upsertNode({ '@id': 'concept:breathwork', '@type': 'Concept', title: 'Breathwork', tags: ['breathwork'] });
  graphStore.upsertNode({ '@id': 'concept:coherence', '@type': 'Concept', title: 'Coherence', tags: ['coherence'] });
  graphStore.addRelation('concept:breathwork', 'concept:coherence', 'extends');
  const related = graphStore.fetchRelated('breathwork', 2);

  const queueStore = createQueueStore({ dbPath: path.join(tmpDir, 'queue.sqlite') });
  const scheduler = createScheduler({
    queueStore,
    graphStore,
    outputDir: path.join(tmpDir, 'outputs')
  });

  scheduler.enqueue({
    name: 'brief_summariser',
    persona_path: path.join(projectRoot, 'sys', 'specialists', 'brief_summariser', 'persona.json'),
    interval_seconds: 120,
    next_allowed_time: '2026-02-09T00:00:00.000Z'
  });
  scheduler.enqueue({
    name: 'memory_promoter',
    persona_path: path.join(projectRoot, 'sys', 'specialists', 'memory_promoter', 'persona.json'),
    interval_seconds: 120,
    next_allowed_time: '2026-02-09T00:00:00.000Z'
  });
  enqueueMaintenanceTasks(queueStore, {
    intervalSeconds: 3600,
    personaPath: path.join(projectRoot, 'sys', 'specialists', 'maintenance_runner', 'persona.json')
  });

  const schedulerRun = scheduler.runOnce('2026-02-09T00:00:10.000Z');

  const rendered = render({
    template: 'brief',
    format: 'html',
    templatesDir: path.join(projectRoot, 'sys', 'templates'),
    data: {
      title: 'System Evolution Brief Sample',
      date: '2026-02-09',
      summary: 'Sample generated from local prototype modules.',
      highlights: {
        first: `Scheduled outputs: ${schedulerRun.ran}`,
        second: `Related nodes: ${related.nodes.length}`
      },
      notes: 'This is a local sample artifact for governance review.'
    }
  });

  const fixturePath = path.join(projectRoot, 'docs', 'fixtures', 'brief_sample.html');
  fs.mkdirSync(path.dirname(fixturePath), { recursive: true });
  fs.writeFileSync(fixturePath, `${rendered.output}\n`, 'utf8');

  const hotReload = await waitForHotReload(configPath);
  appendMigrationLog({
    phase: 'config_hot_reload_trace',
    type: hotReload.type,
    loadedAt: hotReload.loadedAt
  });
  const breathSummary = breath.summary({
    manifestPath: path.join(projectRoot, 'sys', 'knowledge', 'breath', 'evidence', 'manifest.json')
  });

  const output = {
    sample: 'system_evolution_2026-02',
    project_root: projectRoot,
    config_default_model: config.models.default,
    queue_tasks_total: queueStore.listTasks().length,
    queue_runs_recorded: queueStore.listRuns().length,
    scheduler_ran: schedulerRun.ran,
    fetch_related_term: 'breathwork',
    fetch_related_nodes: related.nodes.map((node) => node['@id']),
    rendered_fixture: fixturePath,
    hot_reload_event: {
      type: hotReload.type,
      loadedAt: hotReload.loadedAt
    },
    breath_status: breathSummary.status
  };

  console.log(JSON.stringify(output, null, 2));
  appendMigrationLog({ phase: 'sample_run_complete', output });
  queueStore.close();
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
