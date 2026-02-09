'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { open } = require('../db/sqlite_adapter');

function ensureDir(filePath) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
}

function nowIso() {
  return new Date().toISOString();
}

function createQueueStore(options = {}) {
  const dbPath = options.dbPath || path.join(process.cwd(), 'sys', 'state', 'queue.sqlite');
  ensureDir(dbPath);

  const db = open(dbPath);

  db.exec(`
    CREATE TABLE IF NOT EXISTS tasks (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      persona_path TEXT NOT NULL,
      last_run TEXT,
      next_allowed_time TEXT NOT NULL,
      interval_seconds INTEGER NOT NULL,
      enabled INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS runs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      task_id INTEGER NOT NULL,
      started_at TEXT NOT NULL,
      finished_at TEXT,
      status TEXT NOT NULL,
      output_path TEXT,
      FOREIGN KEY(task_id) REFERENCES tasks(id)
    );
  `);

  const insertTaskStmt = db.prepare(
    `INSERT INTO tasks (name, persona_path, last_run, next_allowed_time, interval_seconds, enabled)
     VALUES (@name, @persona_path, @last_run, @next_allowed_time, @interval_seconds, @enabled)`
  );

  const listTasksStmt = db.prepare(
    `SELECT id, name, persona_path, last_run, next_allowed_time, interval_seconds, enabled
     FROM tasks
     ORDER BY id ASC`
  );

  const claimRunnableStmt = db.prepare(
    `SELECT id, name, persona_path, last_run, next_allowed_time, interval_seconds, enabled
     FROM tasks
     WHERE enabled = 1 AND next_allowed_time <= @nowIso
     ORDER BY next_allowed_time ASC, id ASC`
  );

  const updateTaskScheduleStmt = db.prepare(
    `UPDATE tasks
     SET last_run = @last_run, next_allowed_time = @next_allowed_time
     WHERE id = @id`
  );

  const insertRunStmt = db.prepare(
    `INSERT INTO runs (task_id, started_at, finished_at, status, output_path)
     VALUES (@task_id, @started_at, @finished_at, @status, @output_path)`
  );

  const listRunsStmt = db.prepare(
    `SELECT id, task_id, started_at, finished_at, status, output_path
     FROM runs
     ORDER BY id ASC`
  );

  function enqueueTask(task) {
    const now = nowIso();
    const payload = {
      name: task.name,
      persona_path: task.persona_path,
      last_run: task.last_run || null,
      next_allowed_time: task.next_allowed_time || now,
      interval_seconds: Number(task.interval_seconds || 300),
      enabled: task.enabled === false ? 0 : 1
    };

    const result = insertTaskStmt.run(payload);
    return Number(result.lastInsertRowid);
  }

  function listTasks() {
    return listTasksStmt.all();
  }

  function listRunnableTasks(now = nowIso()) {
    return claimRunnableStmt.all({ nowIso: now });
  }

  function updateTaskSchedule(taskId, nextAllowedTime, lastRun) {
    updateTaskScheduleStmt.run({
      id: Number(taskId),
      last_run: lastRun || nowIso(),
      next_allowed_time: nextAllowedTime
    });
  }

  function recordRun(run) {
    const payload = {
      task_id: Number(run.task_id),
      started_at: run.started_at || nowIso(),
      finished_at: run.finished_at || nowIso(),
      status: run.status || 'ok',
      output_path: run.output_path || null
    };

    const result = insertRunStmt.run(payload);
    return Number(result.lastInsertRowid);
  }

  function listRuns() {
    return listRunsStmt.all();
  }

  function close() {
    db.close();
  }

  return {
    dbPath,
    enqueueTask,
    listTasks,
    listRunnableTasks,
    updateTaskSchedule,
    recordRun,
    listRuns,
    close
  };
}

module.exports = {
  createQueueStore,
  nowIso
};
