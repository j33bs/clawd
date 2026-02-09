'use strict';

function run(context) {
  return {
    summary: `Brief summariser executed for task ${context.task.name}`,
    timestamp: context.now,
    persona: context.persona.name
  };
}

module.exports = {
  run
};
