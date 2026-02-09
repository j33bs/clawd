'use strict';

const { runQuickFix } = require('../../maintenance');

function run(context) {
  const taskName = String(context.task.name || '');
  const fixName = taskName.startsWith('maintenance:') ? taskName.slice('maintenance:'.length) : taskName;
  const result = runQuickFix(fixName, context);

  return {
    task: taskName,
    status: 'ok',
    fix: fixName,
    result
  };
}

module.exports = { run };
