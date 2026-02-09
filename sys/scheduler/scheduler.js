'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { nowIso } = require('./queue_store');

function ensureDir(targetPath) {
  fs.mkdirSync(targetPath, { recursive: true });
}

function plusSeconds(isoTime, seconds) {
  const base = new Date(isoTime).getTime();
  return new Date(base + Number(seconds || 0) * 1000).toISOString();
}

function loadSpecialist(personaPath) {
  const persona = JSON.parse(fs.readFileSync(personaPath, 'utf8'));
  const runPath = path.join(path.dirname(personaPath), 'run.js');
  const specialist = require(runPath);
  if (typeof specialist.run !== 'function') {
    throw new Error(`Specialist run.js missing run() export: ${runPath}`);
  }
  return {
    persona,
    run: specialist.run
  };
}

function createScheduler(options = {}) {
  const queueStore = options.queueStore;
  if (!queueStore) {
    throw new Error('createScheduler requires queueStore');
  }

  const outputDir = options.outputDir || path.join(process.cwd(), 'sys', 'state', 'outputs');
  const graphStore = options.graphStore || null;

  function enqueue(task) {
    return queueStore.enqueueTask(task);
  }

  function runOnce(currentIso = nowIso()) {
    ensureDir(outputDir);
    const runnable = queueStore.listRunnableTasks(currentIso);

    if (runnable.length === 0) {
      return {
        ran: 0,
        outputs: [],
        at: currentIso
      };
    }

    const outputs = [];

    runnable.forEach((task) => {
      const startedAt = nowIso();
      let status = 'ok';
      let outputPath = null;

      try {
        const specialist = loadSpecialist(task.persona_path);
        const result = specialist.run({
          task,
          persona: specialist.persona,
          now: startedAt
        });

        const fileName = `${task.id}-${new Date(startedAt).getTime()}.json`;
        outputPath = path.join(outputDir, fileName);
        fs.writeFileSync(
          outputPath,
          `${JSON.stringify({ task, result, startedAt }, null, 2)}\n`,
          'utf8'
        );

        if (graphStore) {
          const runNodeId = `run:${task.id}:${new Date(startedAt).getTime()}`;
          graphStore.upsertNode({
            '@id': runNodeId,
            '@type': 'Run',
            title: `${task.name} run`,
            path: outputPath,
            tags: ['scheduler-run', task.name]
          });

          const specialistNodeId = `specialist:${specialist.persona.name}`;
          graphStore.upsertNode({
            '@id': specialistNodeId,
            '@type': 'Agent',
            title: specialist.persona.name,
            tags: ['specialist']
          });
          graphStore.addRelation(runNodeId, specialistNodeId, 'learned-from');
        }
      } catch (error) {
        status = 'error';
        outputPath = null;
      }

      const finishedAt = nowIso();
      queueStore.recordRun({
        task_id: task.id,
        started_at: startedAt,
        finished_at: finishedAt,
        status,
        output_path: outputPath
      });

      queueStore.updateTaskSchedule(task.id, plusSeconds(finishedAt, task.interval_seconds), finishedAt);

      outputs.push({
        taskId: task.id,
        name: task.name,
        status,
        outputPath
      });
    });

    return {
      ran: outputs.length,
      outputs,
      at: currentIso
    };
  }

  return {
    enqueue,
    runOnce
  };
}

module.exports = {
  createScheduler,
  plusSeconds
};
