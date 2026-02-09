'use strict';

function run(context = {}) {
  const tasks = Array.isArray(context.tasks) ? context.tasks : [];
  const minIntervalSeconds = Number(context.minIntervalSeconds || 60);
  const violations = tasks.filter((task) => Number(task.interval_seconds || 0) < minIntervalSeconds);

  return {
    name: 'cron_task_sanity_check',
    ok: violations.length === 0,
    violations,
    minIntervalSeconds
  };
}

module.exports = { run };
